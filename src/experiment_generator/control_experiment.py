from payu.git_utils import GitRepository
from payu.branch import checkout_branch
from .f90nml_updater import F90NamelistUpdater
from .config_updater import ConfigUpdater
from .nuopc_runconfig_updater import NuopcRunConfigUpdater
from .base_experiment import BaseExperiment


class ControlExperiment(BaseExperiment):
    """
    Manages the control experiment by updating configuration files and committing changes
    to a Git repository based on a provided YAML input file.
    """

    def __init__(self, directory, indata) -> None:
        super().__init__(indata)
        self.directory = directory
        self.gitrepository = GitRepository(directory)

        # initialise updater for each configuration file
        self.f90namelistupdater = F90NamelistUpdater(directory)
        self.configupdater = ConfigUpdater(directory)
        self.nuopcrunconfigupdater = NuopcRunConfigUpdater(directory)

    # control experiment
    def setup_control_expt(self) -> None:
        """
        Set up the control experiment by updating parameters defined
        in the YAML configuration.

        Supported configuration files:
            - `config.yaml`
            - Fortran namelists (*.nml, *_in)
            - `nuopc.runconfig`
            - (Future support) MOM_input, nuopc.runseq, field_table, XML files

        After updates, changes are committed to the Git repository.
        """
        control_data = self.indata.get("Control_Experiment")

        if not control_data:
            raise ValueError("No control experiment data found in YAML input file!")

        if self.control_branch_name in {
            i.name for i in self.gitrepository.repo.branches
        }:
            # Ensure the repository is on the control branch
            checkout_branch(
                branch_name=self.control_branch_name,
                is_new_branch=False,
                start_point=self.control_branch_name,
                config_path=self.directory / "config.yaml",
            )

        exclude_dirs = {".git", ".github", "testing", "docs"}

        # Iterate over all files and apply updates if matched in control_data
        for file in self.directory.rglob("*"):
            if any(part in exclude_dirs for part in file.parts):
                continue

            target_file = file.relative_to(self.directory)

            # eg, ice/cice_in.nml or ice_in.nml
            yaml_data = control_data.get(str(target_file))

            if yaml_data:
                # Updates config entries from f90nml files
                if target_file.name.endswith("_in") or target_file.suffix == ".nml":
                    self.f90namelistupdater.update_nml_params(yaml_data, target_file)

                # Updates config entries from `config_yaml`
                if target_file.name == "config.yaml":
                    self.configupdater.update_config_params(yaml_data, target_file)

                # Updates nuopc.runconfig entries from `nuopc.runconfig`
                if target_file.name == "nuopc.runconfig":
                    self.nuopcrunconfigupdater.update_runconfig_params(
                        yaml_data, target_file
                    )

        # git commit only if files were actually modified
        modified_files = [
            item.a_path for item in self.gitrepository.repo.index.diff(None)
        ]
        commit_message = f"Updated control files: {modified_files}"
        self.gitrepository.commit(commit_message, modified_files)
