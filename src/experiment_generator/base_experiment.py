from pathlib import Path


class BaseExperiment:
    """
    Manage experiment configuration and shared setup paths.

    This class parses the input dictionary and exposes common attributes
    used by both control and perturbation experiment workflows.
    """

    def __init__(self, indata: dict) -> None:
        self.indata = indata
        self.dir_manager = Path.cwd()

        # General experiment setup
        self.test_path = Path(indata.get("test_path", "experiment_generator_test_path"))
        self.model_type = indata.get("model_type", False)

        # Repository setup
        self.repository = indata.get("repository_url")
        self.repo_dir = indata.get("repository_directory")
        self.directory = Path(self.dir_manager) / self.test_path / self.repo_dir
        self.existing_branch = indata.get("existing_branch", None)
        self.control_branch_name = indata.get("control_branch_name", False)
        self.keep_uuid = indata.get("keep_uuid", False)

        # Restart and configuration paths
        self.restart_path = indata.get("restart_path", None)
        self.parent_experiment = indata.get("parent_experiment", None)
        self.config_path = indata.get("config_path", None)
        self.lab_path = indata.get("lab_path", None)
        self.start_point = indata.get("start_point", None)

        # Experiment mode
        self.perturbation_enabled = indata.get("Perturbation_Experiment", False)
