# access-experiment-generator

[![CI](https://github.com/ACCESS-NRI/access-experiment-generator/actions/workflows/ci.yml/badge.svg)](https://github.com/ACCESS-NRI/access-experiment-generator/actions/workflows/ci.yml)
[![CD](https://github.com/ACCESS-NRI/access-experiment-generator/actions/workflows/cd.yml/badge.svg)](https://github.com/ACCESS-NRI/access-experiment-generator/actions/workflows/cd.yml)
[![Coverage Status](https://codecov.io/gh/ACCESS-NRI/access-experiment-generator/branch/main/graph/badge.svg)](https://codecov.io/gh/ACCESS-NRI/access-experiment-generator)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue?style=flat-square)](https://opensource.org/license/apache-2-0) 
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)


## About
The **ACCESS Experiment Generator** is a tool for creating **ensembles of model experiments** from a single control configuration. Instead of manually editing multiple files, you describe changes in one YAML plan, and the generator:

- Clones the configuration repository from GitHub.  
- Creates a control branch (with optional edits).  
- Creates one new branch per perturbation experiment.  
- Applies the parameter changes and commits them.

Each generated branch is immediately `Payu`-ready — you can step into the branch directory and launch runs on Gadi, NCI using [`Payu`](https://github.com/payu-org/payu).

## Key features
- **YAML-driven configuration**: define edits once, apply them across many experiments.  
- **Git-branch workflow**: each variant is a branch, making experiments traceable.  
- **Reproducibility**: given the same repo + YAML, identical branches are regenerated.  
- **Payu integration**: generated branches are ready to run on [Payu](https://github.com/payu-org/payu).

## Documentation
Full documentation is available at https://access-experiment-generator.access-hive.org.au/

## Installation
### User setup

The `experiment-generator` is installed in the `payu-dev` conda environment:

```bash
module use /g/data/vk83/prerelease/modules && module load payu/dev
```

Alternatively, create a Python virtual environment and install via pip:

```bash
python3 -m venv <path/to/venv> --system-site-packages
source <path/to/venv>/bin/activate

pip install experiment-generator
```

### Development setup
For contributors and developers, setup a development environment,
```
git clone https://github.com/ACCESS-NRI/access-experiment-generator.git
cd access-experiment-generator

# under a virtual environment
pip install -e .
```

## Usage
```bash
$ experiment-generator --help

usage: experiment-generator [-h] [-i INPUT_YAML_FILE]

Manage ACCESS experiments using configurable YAML input.
If no YAML file is specified, the tool will look for 'Experiment_generator.yaml' in the current directory.
If that file is missing, you must specify one with -i / --input-yaml-file.

options:
  -h, --help            show this help message and exit
  -i INPUT_YAML_FILE, --input-yaml-file INPUT_YAML_FILE
                        Path to the YAML file specifying parameter values for experiment runs.
                        Defaults to 'Experiment_generator.yaml' if present in the current directory.
```

## Example YAML
An exmaple plan (`examples/Experiment_generator_example.yaml`)

```yaml
model_type: access-om2 # Specify the model ("access-om2", "access-om3", "access-esm1.5", or "access-esm1.6")
repository_url: git@github.com:ACCESS-NRI/access-om2-configs.git
start_point: "fce24e3" # Control commit hash for new branches
test_path: prototype-0.1.0 # All control and perturbation experiment repositories will be created here; can be relative, absolute or ~ (user-defined)
repository_directory: 1deg_jra55_ryf # Local directory name for the central repository (user-defined)

control_branch_name: ctrl

Control_Experiment:
  accessom2.nml:
    date_manager_nml:
      restart_period: "0,0,86400"

  config.yaml:
    queue: express
    walltime: 5:00:00

  ice/cice_in.nml:
    shortwave_nml:
      albicei: 0.05
      albicev: 0.08
    thermo_nml:
      chio: 0.001

Perturbation_Experiment:
  Parameter_block1:
    branches:
      - perturb_1
      - perturb_2

    ice/cice_in.nml:
      shortwave_nml:
        albicei:
          - 0.06
          - 0.07
        albicev:
          - 0.78
          - 0.81
      thermo_nml:
        chio:
          - 0.007
          - 0.008

    ocean/input.nml:
      ocean_nphysics_util_nml:
        agm_closure_length:
          - 25000.0
          - 75000.0
```

## Workflow example
1. Run the generator
```bash
experiment-generator -i examples/Experiment_generator_example.yaml
```

2. Inspect branches
```bash
cd my-experiment/1deg_jra55_ryf
git branch
# ctrl
# main
# perturb_1
# perturb_2
```

3. Check changes
```bash
git checkout perturb_1
git diff ctrl -- ice/cice_in.nml
```