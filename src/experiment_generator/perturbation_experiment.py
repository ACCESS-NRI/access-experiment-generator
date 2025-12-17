import os
import warnings
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Mapping  # , Sequence  # , Hashable
from payu.branch import checkout_branch
from .base_experiment import BaseExperiment
from payu.git_utils import GitRepository
from .f90nml_updater import F90NamelistUpdater
from .config_updater import ConfigUpdater
from .nuopc_runconfig_updater import NuopcRunConfigUpdater
from .mom6_input_updater import Mom6InputUpdater
from .nuopc_runseq_updater import NuopcRunseqUpdater
from .om2_forcing_updater import Om2ForcingUpdater
from .common_var import BRANCH_KEY, _is_removed_str, _is_preserved_str, _is_seq
from .utils import _strip_preserved
from .state_store import RemoveStateStore


@dataclass
class ExperimentDefinition:
    """
    Data class representing the definition of a perturbation experiment.

    Attributes:
        block_name (str): Top-level blocks (eg Parameter_block) from the YAML configuration.
        branch_name (str): git branch name for this experiment.
        file_params (dict): parameter dictionaries.
    """

    block_name: str
    branch_name: str
    file_params: dict[str, dict]


class PerturbationExperiment(BaseExperiment):
    """
    Class to manage perturbation experiments by applying parameter sensitivity tests.
      - Parsing nested YAML definitions into flat experiment configurations.
      - Creating or checking out Git branches for each perturbation.
      - Applying file-specific parameter updates using relevant updaters.
      - Committing changes on each branch to record the perturbation setup.
    """

    def __init__(self, directory: str | Path, indata: dict) -> None:
        super().__init__(indata)
        self.directory = Path(directory)
        self.gitrepository = GitRepository(self.directory)

        # state store for managing parameter removals
        self.state_store = RemoveStateStore(self.directory)

        # updater for each configuration file
        self.f90namelistupdater = F90NamelistUpdater(directory)
        self.configupdater = ConfigUpdater(directory)
        self.nuopcrunconfigupdater = NuopcRunConfigUpdater(directory)
        self.mom6inputupdater = Mom6InputUpdater(directory)
        self.nuopcrunsequpdater = NuopcRunseqUpdater(directory)
        self.om2forcingupdater = Om2ForcingUpdater(directory)

    def _apply_updates(self, file_params: dict[str, dict], state: dict | None = None) -> None:
        """
        Apply a dict of `{filename: parameters}` to different config files.
        """
        for filename, params in file_params.items():
            # TODO: this is temporary because f90nml_updater.update_nml_params does not use
            # update_config_entries() yet. This will be fixed as long as access-parsers implements.
            should_apply, params = _strip_preserved(params)
            if not should_apply:
                params = {}

            if filename.endswith("_in") or filename.endswith(".nml") or os.path.basename(filename) == "namelists":
                self.f90namelistupdater.update_nml_params(params, filename, state=state)
            elif filename.endswith(".yaml"):
                self.configupdater.update_config_params(params, filename, state=state)
            elif filename == "nuopc.runconfig":
                self.nuopcrunconfigupdater.update_runconfig_params(params, filename, state=state)
            elif filename == "MOM_input":
                self.mom6inputupdater.update_mom6_params(params, filename, state=state)
            elif filename == "nuopc.runseq":
                self.nuopcrunsequpdater.update_nuopc_runseq(params, filename, state=state)
            elif filename == "atmosphere/forcing.json":
                self.om2forcingupdater.update_forcing_params(params, filename, state=state)

    def manage_control_expt(self) -> None:
        """
        Update files for the control branch (name held in `self.control_branch_name`).
        """
        control_data = self.indata.get("Control_Experiment")
        if control_data is None:
            warnings.warn(
                "No Control_Experiment block provided in the input YAML file. " "Skipping control branch updates.",
                UserWarning,
            )
            return

        # Ensure we are on the control branch
        branch_names = {i.name for i in self.gitrepository.repo.branches}
        if self.control_branch_name in branch_names:
            checkout_branch(
                branch_name=self.control_branch_name,
                is_new_branch=False,
                start_point=self.control_branch_name,
                config_path=self.directory / "config.yaml",
            )

        # Walk the repo, skipping un-interesting dirs
        exclude_dirs = {".git", ".github", "testing", "docs"}
        for file in self.directory.rglob("*"):
            if any(part in exclude_dirs for part in file.parts):
                continue
            rel_path = file.relative_to(self.directory)
            # eg, ice/cice_in.nml or ice_in.nml
            yaml_data = control_data.get(str(rel_path))
            if yaml_data:
                self._apply_updates({str(rel_path): yaml_data})

        # Commit if anything actually changed
        modified_files = [item.a_path for item in self.gitrepository.repo.index.diff(None)]
        commit_message = f"Updated control files: {modified_files}"
        self.gitrepository.commit(commit_message, modified_files)

    def manage_perturb_expt(self) -> None:
        """
        Manage the overall perturbation experiment workflow:
          1. Validate presence of perturbation data.
          2. Collect flat list of ExperimentDefinition instances.
          3. Check existing local Git branches.
          4. Loop through each definition:
             a. Set up the branch.
             b. Update experiment files.
             c. Commit modified files.
        """
        # main section, top level key that groups different namelists
        namelists = self.indata.get("Perturbation_Experiment")
        if not namelists:
            warnings.warn(
                "\nNO Perturbation were provided, hence skipping parameter-tunning tests!",
                UserWarning,
            )
            return

        # collect all experiment definitions as a flat list
        experiment_definitions = self._collect_experiment_definitions(namelists)

        # check local branches
        local_branches = self.gitrepository.local_branches_dict()

        # setup each experiment (create branch names and print actions)
        for expt_def in experiment_definitions:
            self._setup_branch(expt_def, local_branches)
            branch = expt_def.branch_name

            state = self.state_store.load_state(branch)

            # then pass state into updates
            self._apply_updates(expt_def.file_params, state=state)

            # save state after updates
            self.state_store.save_state(branch, state)

            modified_files = [item.a_path for item in self.gitrepository.repo.index.diff(None)]
            commit_message = f"Updated perturbation files: {modified_files}"
            self.gitrepository.commit(commit_message, modified_files)

    def _collect_experiment_definitions(self, namelists: dict) -> list[ExperimentDefinition]:
        """
        Collects and returns a list of experiment definitions based on provided perturbation namelists.
        """
        experiment_definitions = []
        for block_name, blockcontents in namelists.items():
            branch_keys = f"{BRANCH_KEY}"
            if branch_keys not in blockcontents:
                warnings.warn(
                    f"\nNO {branch_keys} were provided, hence skipping parameter-sensitivity tests!",
                    UserWarning,
                )
                continue
            branch_names = blockcontents[branch_keys]
            total_exps = len(branch_names)

            # all other keys hold file-specific parameter configurations
            file_params_all = {k: v for k, v in blockcontents.items() if k != branch_keys}

            for indx, branch_name in enumerate(branch_names):
                single_run_file_params = {}
                for filename, param_dict in file_params_all.items():
                    run_specific_params = self._extract_run_specific_params(param_dict, indx, total_exps)
                    single_run_file_params[filename] = run_specific_params

                experiment_definitions.append(
                    ExperimentDefinition(
                        block_name=block_name,
                        branch_name=branch_name,
                        file_params=single_run_file_params,
                    )
                )

        return experiment_definitions

    def _extract_run_specific_params(self, nested_dict: dict, indx: int, total_exps: int) -> dict:
        """
        Recursively extract parameters for a specific run index from nested structures.
        It handles,
         - nested Mappings (dict-like),
         - plain lists, lists of lists, and lists of dicts,
         - broadcasting single values across all branches,
         - removing explicit delete markers (only the literal REMOVED string).

        Rules:
         - Mapping (dict): recursively extract for each key.
         - list of dicts:
            - outer_len == 1; treats as a broadcast, unwraps the inner dict and applies it to all branches.
            - outer_len == total_exps; extracts by index.
            - else -> error (len must equal total_exps)
         - list of lists:
            - if outer length == 1
                - if inner is empty, drops the parent key.
                - if inner is list of dicts, recurses for each dict.
                - else applies _select_from_list to the inner list.
            - if outer length == total_exps: extracts by index.
            - else -> error (len must equal total_exps)
         - plain list (scalars, strings):
            - if outer length == 1: broadcasts the single value to all branches.
            - if outer length == total_exps: extracts by index.
            - else -> error (len must equal total_exps)
         - other scalar / strings: broadcasts the single value to all branches.

         - Special markers:
            -  REMOVE: keep it in the result so that later updaters can drop the key.
            -  PRESERVE: also keep it in the result so that later stripping
              (via _strip_preserved or update_config_entries) decides whether to
              keep or drop it.
            - None or null etc: preserved as-is (not removed).

         -  Filtering:
            - After cleaning, empty lists and empty dicts are dropped (parent key omitted).
            - `None`/null values are preserved as-is (not removed).
        """

        def _filter_value(x):
            """
            Clean values; return (keep: bool, cleaned).
            """
            # Preserve explicit delete marker as a value (not dropped here)
            if _is_removed_str(x):
                return True, x

            if _is_preserved_str(x):
                # keep marker so list merger can interpret it at element level
                return True, x

            # Mapping (dict, CommentedMap, etc); clean values and prune empties
            if isinstance(x, Mapping):
                res = type(x)()
                for k, v in x.items():
                    keep_v, filtered_v = _filter_value(v)
                    if keep_v:
                        res[k] = filtered_v
                return (False, None) if not res else (True, res)

            # Sequence (list etc); clean each element and drop empties/_drop
            if _is_seq(x):
                if len(x) == 1 and _is_preserved_str(x[0]):
                    return True, x

                elements = []
                for v in x:
                    keep_v, filtered_v = _filter_value(v)
                    elements.append(filtered_v)
                return (False, None) if not elements else (True, elements)

            # # Scalar, str, None, etc
            return True, x

        def _select_from_list(row: list):
            """
            Clean a list and select the appropriate element for this run index.
            """
            keep_v, cleaned = _filter_value(row)
            if not keep_v:
                return False, None
            # Propagate literal REMOVE (non-sequence) upwards
            if _is_removed_str(cleaned) and not _is_seq(cleaned):
                return True, cleaned
            return True, cleaned

        result = {}
        for key, value in nested_dict.items():
            # nested dictionary (Mapping)
            if isinstance(value, Mapping):
                keep_v, cleaned = _filter_value(self._extract_run_specific_params(value, indx, total_exps))
                if keep_v:
                    result[key] = cleaned
                continue

            # list or list of dicts/lists (Sequence)
            if isinstance(value, list):
                # if it's a list of dicts (e.g., for submodels in `config.yaml` in OM2)
                if value and all(isinstance(i, Mapping) for i in value):
                    outer_len = len(value)

                    # Clean each item first (so empties fall out)
                    cleaned_items = []
                    for item in value:
                        keep_v, item_clean = _filter_value(self._extract_run_specific_params(item, indx, total_exps))
                        if keep_v:
                            cleaned_items.append(item_clean)
                    if not cleaned_items:
                        continue

                    if outer_len == 1:
                        result[key] = cleaned_items[0]  # broadcast the single dict to all branches
                    elif outer_len == total_exps:
                        result[key] = cleaned_items[indx]  # select by index
                    else:
                        raise ValueError(
                            f"For key '{key}', expected outer list-of-dicts length 1 or {total_exps}, got {outer_len}"
                        )
                    continue

                # list of lists
                if value and all(isinstance(i, list) for i in value):
                    outer_len = len(value)
                    if outer_len == 1:
                        # broadcasting an inner inventory
                        inner = value[0]

                        # if inner is empty, drop the parent key suchas queue: [[]]
                        if isinstance(inner, list) and len(inner) == 0:
                            continue

                        if all(isinstance(d, Mapping) for d in inner):
                            # recurse for each dict
                            items = []
                            for d in inner:
                                items.append(self._extract_run_specific_params(d, indx, total_exps))
                            result[key] = items
                            continue
                        # otherwise, treat as a plain list
                        keep_v, sel = _select_from_list(inner)
                    elif outer_len == total_exps:
                        keep_v, sel = _select_from_list(value[indx])
                    else:
                        raise ValueError(
                            f"For key '{key}', expected outer list-of-lists length 1 or {total_exps}, got {outer_len}"
                        )
                    if keep_v:
                        result[key] = sel
                    # else drop parent key
                    continue

                # Plain list: if it has one element or all elements are identical, broadcast that element.
                if len(value) == 1 or (len(value) > 1 and all(i == value[0] for i in value)):
                    keep_v, sel = _select_from_list(value[0])
                    if keep_v:
                        result[key] = sel
                else:
                    if len(value) != total_exps:
                        raise ValueError(
                            f"For key '{key}', the inner list length is {len(value)}, but the "
                            f"total experiment count is {total_exps}"
                        )
                    keep_v, sel = _select_from_list(value[indx])
                if keep_v:
                    if isinstance(sel, str) and _is_preserved_str(sel):
                        pass
                    else:
                        result[key] = sel
                # else drop parent key
                continue

            if _is_removed_str(value) or _is_preserved_str(value):
                # PRESERVE or REMOVE at scalar level so keep literal marker
                result[key] = value
                continue

            # Scalar, string, etc so return as is
            result[key] = value
        return result

    def _setup_branch(self, expt_def: ExperimentDefinition, local_branches: dict) -> None:
        """
        Set up the Git branch for a perturbation experiment based on its definition.
        """

        branch_existed = expt_def.branch_name in local_branches

        if branch_existed:
            print(f"-- Branch {expt_def.branch_name} already exists, switching to it only!")
            checkout_branch(
                branch_name=expt_def.branch_name,
                is_new_branch=False,
                start_point=expt_def.branch_name,
                config_path=self.directory / "config.yaml",
            )
        else:
            print(f"-- Creating branch {expt_def.branch_name} from {self.control_branch_name}!")
            checkout_branch(
                branch_name=expt_def.branch_name,
                is_new_branch=True,
                keep_uuid=self.keep_uuid,
                start_point=self.control_branch_name,
                restart_path=self.restart_path,
                config_path=self.directory / "config.yaml",
                control_path=self.directory,
                model_type=self.model_type,
                lab_path=self.lab_path,
                parent_experiment=self.parent_experiment,
            )
