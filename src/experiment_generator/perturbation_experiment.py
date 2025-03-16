import warnings
from dataclasses import dataclass
from payu.branch import checkout_branch
from .control_experiment import ControlExperiment


BRANCH_SUFFIX = "_branches"


@dataclass
class ExperimentDefinition:
    """
    Data class representing the definition of a perturbation experiment.
    """

    block_name: str
    branch_name: str
    file_params: dict[str, dict]


class PerturbationExperiment(ControlExperiment):
    """
    Class to manage perturbation experiments by applying parameter sensitivity tests.
    """

    def manage_perturb_expt(self) -> None:
        """
        Manage the overall perturbation experiment workflow:
          - Validate provided perturbation configurations.
          - Collect experiment definitions from the provided namelists.
          - Check for existing local Git branches.
          - Setup and update each experiment branch accordingly.
          - Commit changes after updating experiment files.
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
            self._update_experiment_files(expt_def)

            modified_files = [
                item.a_path for item in self.gitrepository.repo.index.diff(None)
            ]
            commit_message = f"Updated perturbation files: {modified_files}"
            self.gitrepository.commit(commit_message, modified_files)

    def _collect_experiment_definitions(
        self, namelists: dict
    ) -> list[ExperimentDefinition]:
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
            file_params_all = {
                k: v for k, v in blockcontents.items() if k != branch_keys
            }

            for indx, branch_name in enumerate(branch_names):
                single_run_file_params = {}
                for filename, param_dict in file_params_all.items():
                    run_specific_params = self._extract_run_specific_params(
                        param_dict, indx, total_exps
                    )
                    single_run_file_params[filename] = run_specific_params

                experiment_definitions.append(
                    ExperimentDefinition(
                        block_name=block_name,
                        branch_name=branch_name,
                        file_params=single_run_file_params,
                    )
                )

        return experiment_definitions

    def _extract_run_specific_params(
        self, nested_dict: dict, indx: int, total_exps: int
    ) -> dict:
        """
        Recursively extract run-specific parameters from a nested dictionary.
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
                    tmp = [
                        self._extract_run_specific_params(i, indx, total_exps)
                        for i in value
                    ]
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
                                    f"For key '{key}', the inner list length {len(row)}, but the total experiment {total_exps}"
                                )
                            new_list.append(row[indx])
                    result[key] = new_list
                else:
                    # Plain list: if it has one element or all elements are identical, broadcast that element.
                    if len(value) == 1 or (
                        len(value) > 1 and all(i == value[0] for i in value)
                    ):
                        result[key] = value[0]
                    else:
                        if len(value) != total_exps:
                            raise ValueError(
                                f"For key '{key}', the inner list length {len(row)}, but the total experiment {total_exps}"
                            )
                        result[key] = value[indx]
            # Scalar, string, etc so return as is
            else:
                result[key] = value
        return result

    def _setup_branch(
        self, expt_def: ExperimentDefinition, local_branches: dict
    ) -> None:
        """
        Set up the Git branch for a perturbation experiment based on its definition.
        """

        branch_existed = expt_def.branch_name in local_branches

        if branch_existed:
            print(
                f"-- Branch {expt_def.branch_name} already exists, switching to it only!"
            )
            checkout_branch(
                branch_name=expt_def.branch_name,
                is_new_branch=False,
                start_point=expt_def.branch_name,
                config_path=self.directory / "config.yaml",
            )
        else:
            print(
                f"-- Creating branch {expt_def.branch_name} from {self.control_branch_name}!"
            )
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

    def _update_experiment_files(self, expt_def: ExperimentDefinition) -> None:
        """
        Update experiment configuration files based on the provided file parameters.
        """
        for filename, params in expt_def.file_params.items():
            if filename.endswith("_in") or filename.endswith(".nml"):
                self.f90namelistupdater.update_nml_params(params, filename)

            elif filename == "config.yaml":
                self.configupdater.update_config_params(params, filename)
