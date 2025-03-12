import os
from pathlib import Path


class BaseExperiment:
    """
    Initialise with configuration data.
    """

    def __init__(self, indata: dict) -> None:
        self.indata = indata
        self.dir_manager = os.getcwd()
        self.test_path = indata.get("test_path", "experiment_generator_test_path")
        self.model_type = indata.get("model_type", False)
        self.repository = indata.get("repository_url")
        self.repo_dir = indata.get("repository_directory")
        self.directory = Path(self.dir_manager) / self.test_path / self.repo_dir
        self.existing_branch = indata.get("existing_branch", None)
        self.control_branch_name = indata.get("control_branch_name", False)
        self.keep_uuid = indata.get("keep_uuid", False)
        self.restart_path = indata.get("restart_path", None)
        self.parent_experiment = indata.get("parent_experiment", None)
        self.config_path = indata.get("config_path", None)
        self.lab_path = indata.get("lab_path", None)
        self.start_point = indata.get("start_point", None)
        self.perturbation_enabled = indata.get("Perturbation_Experiment", False)
