from payu.branch import clone
from payu.models import index as model_index
from .perturbation_experiment import PerturbationExperiment
from .base_experiment import BaseExperiment
from .source_experiment import apply_source_experiment

# directly use Payu api
# https://github.com/payu-org/payu/blob/master/payu/subcommands/list_cmd.py
VALID_MODELS = tuple(model_index)


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
        # a source run fills in the control experiment source before anything reads it
        apply_source_experiment(indata)
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
            print(f"-- Test dir: {self.directory} already exists, hence not cloning {self.repository_url}")
            return

        try:
            clone(
                repository=self.repository_url,
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
        except Exception as error:
            # Git refuses to read a repository owned by someone else
            # https://github.com/ACCESS-NRI/access-experiment-generator/issues/103
            if "dubious ownership" not in str(error):
                raise
            raise RuntimeError(
                f"Git refuses to read {self.repository_url} because it belongs to another user. "
                f"To add an exception for this directory, call:\n"
                f"    git config --global --add safe.directory {self.repository_url}/.git"
            ) from error
