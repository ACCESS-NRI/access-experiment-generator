import warnings
from pathlib import Path
from dataclasses import dataclass
from payu.branch import checkout_branch
from .base_experiment import BaseExperiment
from payu.git_utils import GitRepository
from .f90nml_updater import F90NamelistUpdater
from .config_updater import ConfigUpdater
from .nuopc_runconfig_updater import NuopcRunConfigUpdater
from .mom6_input_updater import Mom6InputUpdater
from .nuopc_runseq_updater import NuopcRunseqUpdater

BRANCH_SUFFIX = "_branches"


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

    def _apply_updates(self, file_params: dict[str, dict]) -> None:
        """
        Apply a dict of `{filename: parameters}` to different config files.
        """
        for filename, params in file_params.items():
            if filename.endswith("_in") or filename.endswith(".nml"):
                self.f90namelistupdater.update_nml_params(params, filename)
            elif filename == "config.yaml":
                self.configupdater.update_config_params(params, filename)
            elif filename == "nuopc.runconfig":
                self.nuopcrunconfigupdater.update_runconfig_params(params, filename)
            elif filename == "MOM_input":
                self.mom6inputupdater.update_mom6_params(params, filename)
            elif filename == "nuopc.runseq":
                self.nuopcrunsequpdater.update_nuopc_runseq(params, filename)

    def manage_control_expt(self) -> None:
        """
        Update files for the control branch (name held in `self.control_branch_name`).
        """
        control_data = self.indata.get("Control_Experiment")
        if not control_data:
            raise ValueError("No Control_Experiment block provided in the input yaml file.")

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
            branch_keys = f"{block_name}{BRANCH_SUFFIX}"
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
        Handles dicts, lists of scalars, lists of lists, and lists of dicts.
        """
        result = {}
        for key, value in nested_dict.items():
            # nested dictionary
            if isinstance(value, dict):
                result[key] = self._extract_run_specific_params(value, indx, total_exps)
            # list or list of lists
            elif isinstance(value, list):
                # if it's a list of dicts (e.g., for submodels in `config.yaml` in OM2)
                if len(value) > 0 and all(isinstance(i, dict) for i in value):
                    # process each dict in the list for the given column indx
                    tmp = [self._extract_run_specific_params(i, indx, total_exps) for i in value]
                    if all(i == tmp[0] for i in tmp):
                        result[key] = tmp[0]
                    else:
                        result[key] = tmp
                # if it's a list of lists
                elif len(value) > 0 and all(isinstance(i, list) for i in value):
                    new_list = []
                    for row in value:
                        if len(row) == 1:
                            # Broadcast the single element for any index
                            new_list.append(row[0])
                        else:
                            if len(row) != total_exps:
                                raise ValueError(
                                    f"For key '{key}', the inner list length {len(row)}, but the "
                                    f"total experiment {total_exps}"
                                )
                            new_list.append(row[indx])
                    result[key] = new_list
                else:
                    # Plain list: if it has one element or all elements are identical, broadcast that element.
                    if len(value) == 1 or (len(value) > 1 and all(i == value[0] for i in value)):
                        result[key] = value[0]
                    else:
                        if len(value) != total_exps:
                            raise ValueError(
                                f"For key '{key}', the inner list length {len(value)}, but the "
                                f"total experiment {total_exps}"
                            )
                        result[key] = value[indx]
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
