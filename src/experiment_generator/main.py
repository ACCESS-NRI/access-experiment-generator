import argparse

from .utils import read_yaml
from .experiment_generator import ExperimentGenerator


def main():
    """
    Managing ACCESS experiments.

    Args:
        INPUT_YAML_FILE (str, optional):
            Path to the YAML file specifying parameter values for experiment runs.
            Defaults to "Expts_manager.yaml".
    """

    parser = argparse.ArgumentParser(
        description="""
        Manage ACCESS experiments.
        Latest version and help: TODO
        """
    )

    parser.add_argument(
        "INPUT_YAML_FILE",
        type=str,
        nargs="?",
        default="Experiment_manager.yaml",
        help="YAML file specifying parameter values for experiment runs."
        "Default is Experiment_manager.yaml",
    )

    args = parser.parse_args()
    input_yaml = args.INPUT_YAML_FILE
    indata = read_yaml(input_yaml)
    generator = ExperimentGenerator(indata)
    generator.run()


if __name__ == "__main__":
    main()
