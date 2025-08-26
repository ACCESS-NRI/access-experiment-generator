Welcome to the access-experiment-generator wiki!

# Overview

The **Experiment Generator** is a tool designed to streamline the creation of one or more experiment configurations from a base “control” experiment setup. Its primary goal is to reduce manual editing and ensure consistent, repeatable workflows, especially when creating large ensembles of experiments. By automating the generation of multiple experiment variants (e.g. parameter perturbations), the **Experiment Generator** helps researchers efficiently explore sensitivity studies and runs.

# Why perturbation experiments?
Climate models contain thousands of uncertain parameters. Systematically varying them helps you:

- Quantify sensitivity (which parameters matter most)
- Assess uncertainty (ensembles instead of single runs)
- Tune models (match observations more robustly)
- Test robustness (are conclusions stable across settings?)
- Document provenance (every variant is versioned)

# Key features

## 1. Parameter perturbation via YAML input

Users define a suite of parameter changes in a YAML configuration file (the “experiment plan”). Each set of changes corresponds to a new experiment variant. The generator:

 - Reads the YAML file,
 - [Optional] Applies the changes to the control experiment configuration files,
 - Produces modified configurations for each variant.

For example, you specify different values for certain Fortran namelist parameters or YAML config options for each run. The generator applies these automatically, producing all the modified configurations in one go - no manual edits required.

## 2. Branch-based version control workflow

The generator uses Git branching to manage the new experiments. 

- Start from a control experiment on a given Git branch or commit, 
- Create a new Git branch for each perturbation experiment,
- Appliy the parameter changes, and commits them on that branch. 

This means each experiment variant is stored on its own branch in the repository, keeping them isolated and traceable. Researchers can easily track changes, revert if necessary, and even push these branches to a remote repository for collaboration or archival. The branch-based approach ensures that large ensembles are organised and that the provenance of each experiment configuration is captured in version control.

## 3. Consistent and repeatable ensemble generation

By using a scripted approach, the experiment creation process is reproducible. Given the same control setup and the same YAML input file, the generator will always produce identical experiment branches. This consistency helps with debugging and sharing experiment setups - anyone with the YAML specification and base repository can regenerate the ensemble. It eliminates the risk of human error when copying files or editing parameters by hand across tens or hundreds of runs.

## 4. Payu integration

The generator fits into the ACCESS modelling workflow and is designed to work with [Payu](https://github.com/payu-org/payu). While generating the experiments doesn’t require running them, this integration suggests the generator can prepare experiments that are immediately ready to be launched on HPC systems (currently Gadi, NCI) via standard tools.

# Installation & setup

## User setup

The `experiment-generator` is installed in the `payu-dev` conda environment, hence loading `payu/dev` would directly make `experiment-generator` available for use.

```
module use /g/data/vk83/prerelease/modules && module load payu/dev
```

Alternatively, create and activate a python virtual environment, then install via `pip`,

```
python3 -m venv <path/to/venv> --system-site-packages
source <path/to/venv>/bin/activate

pip install experiment-generator
```

or install from the `accessnri` conda channel,

```
conda install -c accessnri experiment-generator
```

After installation, verify the setup by checking,

```bash
$ experiment-generator --help
usage: experiment-generator [-h] [-i INPUT_YAML_FILE]

Manage ACCESS experiments using configurable YAML input.
If no YAML file is specified, the tool will look for 'Experiment_manager.yaml' in the current directory.
If that file is missing, you must specify one with -i / --input-yaml-file.

options:
  -h, --help            show this help message and exit
  -i INPUT_YAML_FILE, --input-yaml-file INPUT_YAML_FILE
                        Path to the YAML file specifying parameter values for experiment runs.
                        Defaults to 'Experiment_manager.yaml' if present in the current directory.
```

## Development setup

for contributors and developers, setup a development environment,

```
git clone https://github.com/ACCESS-NRI/access-experiment-generator.git
cd access-experiment-generator

# under a virtual environment
pip install -e .
```

# Quick start

## Basic workflow
The generator:

- Reads a YAML configuration file describing control and perturbation edits
- Clones the model configuration repository
- Creates a control branch (optional edits)
- Creates one branch per perturbation experiment
- Applies edits to each branch and commits them

## Example: Create your first configuration
A demonstration example can be found in [examples/Experiment_generator_example.yaml](https://github.com/ACCESS-NRI/access-experiment-generator/blob/main/examples/Experiment_generator_example.yaml)

### Step 1 - minimal YAML

```yaml
model_type: access-om2
repository_url: git@github.com:ACCESS-NRI/access-om2-configs.git
start_point: "fce24e3"
test_path: my-experiment
repository_directory: 1deg_jra55_ryf
control_branch_name: ctrl

Control_Experiment:
  # Control experiment parameters

Perturbation_Experiment:
  # Parameter variations
```
This tells the generator to:

- Clone `ACCESS-NRI/access-om2-configs` at commit `fce24e3`,
- Create a working directory `my-experiment`, which include all the experiments,
- Use `1deg_jra55_ryf` inside as the central config hub.

### Step 2 - Control edits
#### Example directory

Below is a filtered view showing three example files - `accessom2.nml`, `cice_in.nml`, `config.yaml` - selected for demonstration purposes. 

```bash
1deg_jra55_ryf]$ tree -P "accessom2.nml|cice_in.nml|config.yaml"
.
├── accessom2.nml
├── atmosphere
├── config.yaml
├── doc
├── ice
│   └── cice_in.nml
├── manifests
├── ocean
├── testing
│   └── checksum
└── tools

8 directories, 3 files
```
The snippets below show the original parameter values that will be changed in each file. 

#### Snapshots of the original parameters in these three files
```f90
1deg_jra55_ryf]$ sed -n '6p;7p;8p;9p' accessom2.nml 
&date_manager_nml
    forcing_start_date = '1900-01-01T00:00:00'
    forcing_end_date = '1901-01-01T00:00:00'
    restart_period = 0,0,86400
```

```f90
1deg_jra55_ryf]$ sed -n '10p;11p' config.yaml 
queue: express
walltime: 5:00:00
```

```f90
$ sed -n '78p;81p;106p;109p;110p' ice/cice_in.nml 
&thermo_nml
    chio = 0.008
&shortwave_nml
    albicei = 0.39
    albicev = 0.81
```
To represent these edits in your YAML plan, place them under the `Control_Experiment` key. For each file:

> [!IMPORTANT]
> Specify the file name exactly as it appears in the repository.
>
> Preserve the correct hierarchy to match the file structure.

For example, 

- In `accessom2.nml`, the Fortran namelist parameter `restart_period` is inside the `date_manager_nml` group, so the YAML hierarchy must reflect this parent–child relationship.
- In `config.yaml`, parameters such as `queue` and `walltime` appear at the top level, so they can be listed directly.
- For files inside subdirectories (e.g. `ice/cice_in.nml`), use the relative path from the repository to the file, then follow the same hierarchy-matching approach.

#### Corresponding control edits in YAML:
```
Control_Experiment:
  accessom2.nml:
    date_manager_nml:
      restart_period: '0,0,86400'

  config.yaml:
    queue: express
    walltime: 5:00:00

  ice/cice_in.nml:
    shortwave_nml:
      albicei: 0.05
      albicev: 0.08
    thermo_nml:
      chio: 0.001
```
> [!NOTE]
> `Control_Experiment` is a required YAML key - the parser depends on it being present.
>
> If you don’t want to change anything in the `ctrl` branch, you can just leave it empty (no file paths or parameters underneath).

After running the generator such as follows, a new `ctrl` branch is created with these changes committed.

```
experiment-generator -i examples/Experiment_generator_example.yaml
```

After this, a new branch named `ctrl` is created alongside the `main` branch. In the `ctrl` branch, the specified parameters are updated, and the Git commit history clearly records which files were modified in each commit.

```bash
$ git branch
  ctrl
  main
```

```bash
commit bae39870bbeb1fb6dba9fa4544673e001dadcd6d (HEAD -> ctrl)
Author: minghangli-uni <24727729+minghangli-uni@users.noreply.github.com>
Date:   Thu Aug 14 09:28:17 2025 +1000

    Updated control files: ['accessom2.nml', 'config.yaml', 'ice/cice_in.nml']
```
### Step 3 - Perturbations
A `Perturbation_Experiment` block in the YAML file defines a set of related experiment runs that share a common purpose — for example, testing different values for one or more model parameters.

Below is a simple example:

```yaml
Perturbation_Experiment:
    Parameter_block1:
        Parameter_block1_branches:  [perturb_1, perturb_2]
        ice/cice_in.nml:
            shortwave_nml:
                albicei:            [0.36     , 0.39]
                albicev:            [0.78     , 0.81]

            thermo_nml:
                chio:               [0.007    , 0.008]

        ocean/input.nml:
            ocean_nphysics_util_nml:
                agm_closure_length: [2.5e4    , 7.5e4]
```
#### For this structure:
1. `Parameter_block1` is the name of this perturbation block. You can name blocks however you like; each block groups a set of related runs.
2. `Parameter_block1_branches` lists the branch names to be created for the runs in this block — here, `perturb_1` and `perturb_2`. These will become new Git branches starting from the control branch (e.g., `ctrl`).
3. The remaining keys specify which configuration files to edit for each run and what values to apply.
 - File paths are relative to the control experiment directory (`repository_directory`).
 - The structure inside each file entry mirrors the file own format, eg,
    - Fortran namelist parameters are grouped under their `&namelist_group_name` (as in `shortwave_nml` or `thermo_nml`),
    - YAML configuration files follow their native key hierarchy

> [!IMPORTANT]
> You can have one or more perturbation blocks in the same YAML.
> 
> The branch list key must be named `<blockname>_branches` — for example, `Parameter_block1_branches` for `Parameter_block1`.

#### How the generator processes a block

For the example above, the generator will:

1. Start from the control branch (`ctrl`).
2. For each branch in `Parameter_block1_branches`:
 - Create the branch from control (or check it out if it already exists).
 - Apply the parameter values corresponding to that branch index:
   - `perturb_1` uses the first value in each list (`albicei=0.36`, `agm_closure_length=2.5e4`, etc.).
   - `perturb_2` uses the second value in each list (`albicei=0.39`, `agm_closure_length=7.5e4`, etc.).
 - Commit the changes so the branch contains only its intended modifications.

This approach makes it easy to:
 - Vary multiple parameters at once across a set of runs,
 - Ensure each run’s configuration is reproducible and stored in Git,
 - Keep experiments organised and traceable, with each branch representing a single perturbation case.



