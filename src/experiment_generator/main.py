import argparse

from .utils import read_yaml
from .experiment_generator import ExperimentGenerator


def main():
    """
    Managing ACCESS experiment generation.

    This script loads experiment configurations from a YAML file
    and invokes the ExperimentGenerator to produce the required setups.

    Command-line Arguments:
        --input-yaml-file (str, optional):
            Path to the YAML file specifying parameter values for the experiment runs.
            Defaults to 'Experiment_manager.yaml'.
    """

    parser = argparse.ArgumentParser(
        description="""
        Manage ACCESS experiments using configurable YAML input.
        This tool helps generate control and perturbation experiments.
        Latest version and help: TODO
        """
    )

    parser.add_argument(
        "--input-yaml-file",
        type=str,
        nargs="?",
        default="Experiment_manager.yaml",
        help=(
            "Path to the YAML file specifying parameter values for experiment runs.\n"
            "If not provided, defaults to 'Experiment_manager.yaml'."
        ),
    )

    args = parser.parse_args()

    # Load the YAML file
    input_yaml = args.input_yaml_file
    indata = read_yaml(input_yaml)

    # Run the experiment generator
    generator = ExperimentGenerator(indata)
    generator.run()


if __name__ == "__main__":
    main()
