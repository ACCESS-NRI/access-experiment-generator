import warnings
from dataclasses import dataclass
from .control_experiment import ControlExperiment
from payu.branch import checkout_branch


@dataclass
class ExperimentDefinition:
    """
    Data class representing the definition of a perturbation experiment.
    """

    block_name: str
    run_name: str
    branch_name: str
    file_params: dict[str, dict]


class PerturbationExperiment(ControlExperiment):
    """
    Class to manage perturbation experiments by applying parameter sensitivity tests.
    """

    def __init__(self, directory, indata) -> None:
        super().__init__(directory, indata)

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
            dir_key = f"{block_name}_dirs"
            if dir_key not in blockcontents:
                warnings.warn(
                    f"\nNO {dir_key} were provided, hence skipping parameter-sensitivity tests!",
                    UserWarning,
                )
                continue
            run_names = blockcontents[dir_key]

            # all other keys hold file-specific parameter configurations
            file_params_all = {k: v for k, v in blockcontents.items() if k != dir_key}

            for indx, run_name in enumerate(run_names):
                single_run_file_params = {}
                for filename, param_dict in file_params_all.items():
                    run_specific_params = self._extract_run_specific_params(
                        param_dict, indx
                    )
                    single_run_file_params[filename] = run_specific_params

                # Create a new branch name from the block name and run name
                branch_name = f"{block_name}/{run_name}"
                experiment_definitions.append(
                    ExperimentDefinition(
                        block_name=block_name,
                        run_name=run_name,
                        branch_name=branch_name,
                        file_params=single_run_file_params,
                    )
                )

        return experiment_definitions

    def _extract_run_specific_params(self, nested_dict: dict, indx: int) -> dict:
        """
        Recursively extract run-specific parameters from a nested dictionary.
        """
        result = {}
        for key, value in nested_dict.items():
            # nested dictionary
            if isinstance(value, dict):
                result[key] = self._extract_run_specific_params(value, indx)
            # list or list of lists
            elif isinstance(value, list):
                # if it's a list of lists
                if len(value) > 0 and all(isinstance(i, list) for i in value):
                    # each row in `value` so pick the indx-th column
                    # eg value = [ [a0,a1], [b0,b1] ] => run #0 -> [a0,b0], run #1 -> [a1,b1]
                    result[key] = [row[indx] for row in value]
                else:
                    # plain list => pick one element by index
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
            print(self.directory)
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
