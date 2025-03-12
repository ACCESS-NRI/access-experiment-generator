import os
from payu.branch import clone
from .control_experiment import ControlExperiment
from .perturbation_experiment import PerturbationExperiment
from .base_experiment import BaseExperiment

# can be extended to include other models
VALID_MODELS = ("access-om2", "access-om3")


class ExperimentGenerator(BaseExperiment):
    """
    Handles setup, cloning, and running control & perturbation experiments.
    """

    def __init__(self, indata: dict):
        super().__init__(indata)

    def run(self) -> None:
        """
        Main function to set up experiments.
        """
        self._create_test_path()
        self._validate_model_type()
        self._clone_repository()
        self._run_control_experiment()
        if self.perturbation_enabled:
            self._run_perturbation_experiment()

    def _create_test_path(self) -> None:
        """
        Creates the test directory if it doesn't exist.
        """
        if os.path.exists(self.test_path):
            print(f"-- Test directory {self.test_path} already exists!")
        else:
            os.makedirs(self.test_path)
            print(f"-- Test directory {self.test_path} has been created!")

    def _validate_model_type(self) -> None:
        """
        Ensures the model type is correct.
        """
        if self.model_type not in VALID_MODELS:
            raise ValueError(f"{self.model_type} must be either {VALID_MODELS}!")

    def _clone_repository(self) -> None:
        """
        Clones the experiment repository if it doesn't already exist.
        """
        if self.directory.exists():
            print(
                f"-- Test dir: {self.directory} already exists, hence not cloning {self.repository}"
            )
        else:
            clone(
                repository=self.repository,
                directory=self.directory,
                branch=self.existing_branch,
                keep_uuid=self.keep_uuid,
                model_type=self.model_type,
                config_path=self.config_path,
                lab_path=self.lab_path,
                new_branch_name=self.control_branch_name,
                restart_path=self.restart_path,
                parent_experiment=self.parent_experiment,
                start_point=self.start_point,
            )

    def _run_control_experiment(self) -> None:
        """
        Runs the control experiment.
        """
        control_experiment = ControlExperiment(self.directory, self.indata)
        control_experiment.setup_control_expt()

    def _run_perturbation_experiment(self) -> None:
        """
        Runs the perturbation experiment if enabled.
        """
        perturbation_experiment = PerturbationExperiment(self.directory, self.indata)
        perturbation_experiment.manage_perturb_expt()
