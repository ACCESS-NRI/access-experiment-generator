import os
import warnings
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Mapping, Sequence  # , Hashable
from payu.branch import checkout_branch
from .base_experiment import BaseExperiment
from payu.git_utils import GitRepository
from .f90nml_updater import F90NamelistUpdater
from .config_updater import ConfigUpdater
from .nuopc_runconfig_updater import NuopcRunConfigUpdater
from .mom6_input_updater import Mom6InputUpdater
from .nuopc_runseq_updater import NuopcRunseqUpdater
from .om2_forcing_updater import Om2ForcingUpdater
from .common_var import REMOVED, BRANCH_KEY


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

        # updater for each configuration file
        self.f90namelistupdater = F90NamelistUpdater(directory)
        self.configupdater = ConfigUpdater(directory)
        self.nuopcrunconfigupdater = NuopcRunConfigUpdater(directory)
        self.mom6inputupdater = Mom6InputUpdater(directory)
        self.nuopcrunsequpdater = NuopcRunseqUpdater(directory)
        self.om2forcingupdater = Om2ForcingUpdater(directory)

    def _apply_updates(self, file_params: dict[str, dict]) -> None:
        """
        Apply a dict of `{filename: parameters}` to different config files.
        """
        for filename, params in file_params.items():
            if filename.endswith("_in") or filename.endswith(".nml") or os.path.basename(filename) == "namelists":
                self.f90namelistupdater.update_nml_params(params, filename)
            elif filename.endswith(".yaml"):
                self.configupdater.update_config_params(params, filename)
            elif filename == "nuopc.runconfig":
                self.nuopcrunconfigupdater.update_runconfig_params(params, filename)
            elif filename == "MOM_input":
                self.mom6inputupdater.update_mom6_params(params, filename)
            elif filename == "nuopc.runseq":
                self.nuopcrunsequpdater.update_nuopc_runseq(params, filename)
            elif filename == "atmosphere/forcing.json":
                self.om2forcingupdater.update_forcing_params(params, filename)

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
            self._apply_updates(expt_def.file_params)

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
         - list of dicts: recurse each dict, if all dicts are the same, return a single dict.
         - list of lists:
            - if outer length == 1: treats as a broadcast, unwraps the inner list and applies it to all branches.
            - if outer length == total_exps: extracts by index.
         - plain list (scalars, strings):
            - if outer length == 1: broadcasts the single value to all branches.
            - if outer length == total_exps: extracts by index.
            - else -> error (len must equal total_exps)
         - other scalar / strings: broadcasts the single value to all branches.

         -  Filtering:
            - In lists/mappings, the literal `REMOVE` string in elements/values is dropped.
                - None/empty value (`null`, `~`, ``) are preserved as-is.
                - any list element that becomes an empty dict after cleaning is dropped - (OM2-forcing specific tidy-up)
        """

        class _Drop:
            """
            marker used internally to indicate a key/element should be dropped.
            """

            pass

        _drop = _Drop()

        def _is_removed_str(x) -> bool:
            return isinstance(x, str) and x == REMOVED

        def _is_seq(x) -> bool:
            return isinstance(x, Sequence) and not isinstance(x, str)

        def _filter_value(x):
            """
            Recursively apply removal rules to any shape; returns:
                - the cleaned value,
                - or the _drop marker to indicate the parent should drop this key/element.

            Rules:
                - preserve the explicit delete marker `REMOVE` when encountered as a value;
                  callers decide whether to drop keys or propagate the marker.
                - Remove list elements that are `REMOVE`.
                - Remove keys whose filtered value is an empty list or `_drop`.
                - Remove empty dicts.
            """
            # Preserve explicit delete marker as a value (not dropped here)
            if _is_removed_str(x):
                return x

            # Mapping (dict, CommentedMap, etc); clean values and prune empties
            if isinstance(x, Mapping):
                res = type(x)()
                for k, v in x.items():
                    filtered_v = _filter_value(v)
                    if filtered_v is _drop:
                        # remove this key
                        continue
                    # if _is_seq(filtered_v) and len(filtered_v) == 0:
                    #     # remove this key if the filtered value is an empty list
                    #     continue
                    # keep this key
                    res[k] = filtered_v
                if not res:
                    # if the dict is empty after filtering, drop it
                    return _drop
                return res
            # Sequence (list, tuple, etc); clean each element and drop empties/_drop
            if _is_seq(x):
                # filter each element, preserve type
                elements = []
                for v in x:
                    if isinstance(v, str) and v == REMOVED:  # drop list element marked REMOVE
                        continue
                    filtered_v = _filter_value(v)
                    # if filtered_v is _drop:
                    #     # remove this element
                    #     continue
                    if _is_seq(filtered_v) and len(filtered_v) == 0:
                        # remove this element if it's an empty list
                        continue
                    # keep this element
                    elements.append(filtered_v)
                return elements
            # # Scalar, str, None, etc
            # if isinstance(x, Hashable) and x in REMOVED:
            #     return _drop
            return x

        def _filter_list(lst: list) -> list:
            """
            Filter a list and always return a (possible empty) list.
            """
            res = _filter_value(lst)
            return list(res)

        def _list_select_and_clean(row: list | str | None) -> list | str | None:
            """
            select one entry from a list context and clean it.
            returns a cleaned value/list or `_drop` to indicate parent-key removal.
            """
            if isinstance(row, list):
                cleaned = _filter_list(row)
                return cleaned if cleaned else _drop  # empty list selection drops parent key
            elif isinstance(row, str) and row == REMOVED:
                return _drop  # selecting REMOVE from plain list drops parent key
            else:
                return row

        result = {}
        for key, value in nested_dict.items():
            # nested dictionary (Mapping)
            if isinstance(value, dict):
                tmp = self._extract_run_specific_params(value, indx, total_exps)
                cleaned = _filter_value(tmp)
                if cleaned is not _drop:
                    result[key] = cleaned
            # list or list of lists (Sequence)
            elif isinstance(value, list):
                # if it's a list of dicts (e.g., for submodels in `config.yaml` in OM2)
                if value and all(isinstance(i, dict) for i in value):
                    # process each dict in the list for the given column indx
                    tmp = [self._extract_run_specific_params(i, indx, total_exps) for i in value]
                    result[key] = tmp[0] if all(x == tmp[0] for x in tmp) else tmp
                # if it's a list of lists
                elif value and all(isinstance(i, list) for i in value):
                    outer_len = len(value)
                    if outer_len == 1:
                        sel = _list_select_and_clean(value[0])
                    elif outer_len == total_exps:
                        sel = _list_select_and_clean(value[indx])
                    else:
                        raise ValueError(
                            f"For key '{key}', expected outer list-of-lists length 1 or {total_exps}, got {outer_len}"
                        )
                    if sel is not _drop:
                        result[key] = sel
                else:
                    # Plain list: if it has one element or all elements are identical, broadcast that element.
                    if len(value) == 1 or (len(value) > 1 and all(i == value[0] for i in value)):
                        sel = _list_select_and_clean(value[0])
                    else:
                        if len(value) != total_exps:
                            raise ValueError(
                                f"For key '{key}', the inner list length is {len(value)}, but the "
                                f"total experiment count is {total_exps}"
                            )
                        sel = _list_select_and_clean(value[indx])
                    if sel is not _drop:
                        result[key] = sel
            # Scalar, string, etc so return as is
            else:
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
