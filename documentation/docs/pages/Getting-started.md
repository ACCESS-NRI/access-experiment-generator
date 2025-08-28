
# Getting started

## Installation

### Option A – on Gadi, NCI (recommended for users)

The `experiment-generator` is installed in the `payu-dev` conda environment (hopefully to be installed in `payu` conda environemnt soon), hence loading `payu/dev` would directly make `experiment-generator` available for use.

```
module use /g/data/vk83/prerelease/modules && module load payu/dev
```

### Option B – virtualenv

Alternatively, create and activate a python virtual environment, then install via pip,

```
python3 -m venv <path/to/venv> --system-site-packages
source <path/to/venv>/bin/activate

pip install experiment-generator
```

### Option C - clone the repository

For contributors and developers, setup a development environment,
```
git clone https://github.com/ACCESS-NRI/access-experiment-generator.git
cd access-experiment-generator

python3 -m venv <path/to/venv> --system-site-packages
source <path/to/venv>/bin/activate

pip install -e .
```

### Usage

The tool only requires a single YAML file, where examples are provided in [access-experiment-generator/examples](https://github.com/ACCESS-NRI/access-experiment-generator/tree/main/examples).

```
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

## Quick start

Create a minimal YAML (save as `Experiment_generator.yaml`),

```
model_type: access-om2
repository_url: git@github.com:ACCESS-NRI/access-om2-configs.git
start_point: "fce24e3"
test_path: my-experiment
repository_directory: 1deg_jra55_ryf
control_branch_name: ctrl

Control_Experiment:


Perturbation_Experiment:
  Parameter_block1:
    branches:
      - perturb_1
      - perturb_2
    ice/cice_in.nml:
      shortwave_nml:
        albicei:
          - 0.36
          - 0.39
```

Run the generator,

```
experiment-generator -i Experiment_generator.yaml
```

You’ll get,

- a `ctrl` branch without edits
- `perturb_1`, `perturb_2` branches with their respective parameter values committed


