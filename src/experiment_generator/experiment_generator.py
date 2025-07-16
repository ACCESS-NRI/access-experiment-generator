from payu.branch import clone
from .perturbation_experiment import PerturbationExperiment
from .base_experiment import BaseExperiment

# can be extended to include other models
VALID_MODELS = ("access-om2", "access-om3")


class ExperimentGenerator(BaseExperiment):
    """
    Main class for setting up and managing ACCESS experiments.

    This class coordinates the full experiment lifecycle, including:
    - Validating model type
    - Cloning necessary repositories
    - Running control experiments
    - Running perturbation experiments (if enabled)
    """

    def __init__(self, indata: dict):
        """
        Initialise the ExperimentGenerator with parsed input configuration.

        Args:
            indata (dict): Dictionary containing input settings from the YAML input.
        """
        super().__init__(indata)

    def run(self) -> None:
        """
        Main function to set up experiments.
        """
        self._create_test_path()
        self._validate_model_type()
        self._clone_repository()
        experiment = PerturbationExperiment(self.directory, self.indata)
        experiment.manage_control_expt()
        if self.perturbation_enabled:
            experiment.manage_perturb_expt()

    def _create_test_path(self) -> None:
        """
        Creates the test directory if it doesn't exist.
        """
        if self.test_path.exists():
            print(f"-- Test directory {self.test_path} already exists!")
        else:
            self.test_path.mkdir(parents=True, exist_ok=True)
            print(f"-- Test directory {self.test_path} has been created!")

    def _validate_model_type(self) -> None:
        """
        Ensures the model type is supported.
        """
        if self.model_type not in VALID_MODELS:
            raise ValueError(f"{self.model_type} must be either {VALID_MODELS}!")

    def _clone_repository(self) -> None:
        """
        Clones the experiment repository if it doesn't already exist.
        """
        if self.directory.exists():
            print(f"-- Test dir: {self.directory} already exists, hence not cloning {self.repository}")
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
