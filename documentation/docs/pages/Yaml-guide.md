
# YAML Guide

Your experiment plan is a YAML file. This section explains how to write it correctly.

## 1. Top-level keys

| Key                   | Example                                              | Description                         |
|-----------------------|------------------------------------------------------|-------------------------------------|
| `model_type`          | `access-om2`                                         | Model/config type, can be either `access-om2`, `access-om3`, `access-esm1.5` or `access-esm1.6`.                   |
| `repository_url`      | `git@github.com:ACCESS-NRI/access-om2-configs.git`   | Git repo to clone for the control experiment.                   |
| `start_point`         | `fce24e3`                                            | Commit/branch to start from         |
| `test_path`           | `prototype-0.1.0`                                 | Workspace directory                 |
| `repository_directory`| `1deg_jra55_ryf`                                     | Subdir containing configs           |
| `control_branch_name` | `ctrl`                                               | Control branch name             |
| `Control_Experiment`  |           | Edits to apply to control branch    |
| `Perturbation_Experiment` | see below                                        | Blocks of perturbations             |

## 2. Control experiment edits

In many cases, you might want your `ctrl` branch to have some modifications relative to the remote branch. For example, you might need to change a few default parameters for all experiments. If so, you list those under `Control_Experiment` in the YAML. If you don't need any changes in the control, you can leave it empty or omit parameters, **but the key `Control_Experiment` should still be present, even if empty**.

For example, suppose in the [`examples/Experiment_generator_example.yaml`](https://github.com/ACCESS-NRI/access-experiment-generator/blob/main/examples/Experiment_generator_example.yaml), we want to adjust the run length and job queue for all experiments. We identify the relevant files and parameters (such as - `accessom2.nml` namelist file, and Payu configuration `config.yaml` for job settings). Those appear as,

- `accessom2.nml` – containing a `&date_manager_nml` fortran namelist group with `restart_period` setting.
- `config.yaml` – containing job submission settings like `queue` and `walltime`.

```yaml
Control_Experiment:
    accessom2.nml:
        date_manager_nml:
            restart_period: "0,0,86400"

    config.yaml:
        queue: express
        walltime: 5:00:00
```

Some notes:
 - File paths are relative to the `repository_directory` (e.g., `ice/cice_in.nml` is a file under `1deg_jra55_ryf/ice` directory in the cloned repo, where `1deg_jra55_ryf` is the `repository_directory`).
 - The YAML hierarchy must mirror the structure of the file, such as in `accessom2.nml`, `restart_period` is inside the namelist group `&date_manager_nml`, so we nest it under `date_manager_nml` in YAML.
 - The values are given as strings where necessary (for example, the `restart_period` has commas, so we put it in quotes).

If `Control_Experiment` is provided, the generator will create the new `ctrl` branch and apply these changes there. It will then commit the changes on that branch. After running the tool, if we check our Git branches, we would see `ctrl` alongside the original branch:

```bash
$ experiment-generator -i my_experiment_plan.yaml
$ cd my-experiment/1deg_jra55_ryf
$ git branch
  ctrl
  main
```

## 3. Define perturbation experiments

Now for the core part: under `Perturbation_Experiment` in the YAML, we describe one or more sets of experiments and the parameter changes for each. Each set of experiments is defined as a block with a name. For example, let's create one block named `Parameter_block1` with two experiments in it. In YAML it might look like:

```yaml
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

    ocean/input.nml:
      ocean_nphysics_util_nml:
        agm_closure_length:
          - 25000.0
          - 75000.0
```

Breaking down this structure:

 - `Parameter_block1` is an arbitrary name for this group of experiments (you can choose a meaningful name). We could have multiple blocks (e.g., `Parameter_block2`, etc.) if we want to organise experiments into different groups.
 - Inside that, the special key `branches` (it must be named `branches` under the block) lists the new branch names to create: here `perturb_1` and `perturb_2`. So we will get two branches from `ctrl` named `perturb_1` and `perturb_2`.
 - The other keys under `Parameter_block1` are file names (same format as in `Control_Experiment`). Here we have two files being changed: `ice/cice_in.nml` and `ocean/input.nml`. Under each, we specify which parameters to modify.
 - For each parameter, we give a list of values – one for each experiment branch. For example, under shortwave_nml we set `albicei: [0.36, 0.39]`. This means in branch `perturb_1` (index 0) `albicei` will be 0.36, and in branch `perturb_2` (index 1) it will be 0.39. Likewise `albicev` is 0.78 in pertu`r`b_1 and 0.81 in `perturb_2`. In `ocean/input.nml`, the namelist parameter `agm_closure_length` takes two values (25000.0 and 75000.0).
 - The generator will iterate through each branch and apply the corresponding values. Each branch is created from `ctrl`, the values for that branch index are applied to the files, and the changes committed with a message indicating perturbation updates.

Some rules to note: 

 - If you provide a single value instead of a list, that value is taken to apply to all experiments (broadcasted).
 - All lists should either have length equal to the number of experiments or be of length 1 (or all elements identical) to be broadcast. If a list length doesn't match and isn't broadcastable, the tool will raise an error to alert you (for example, two values given for three experiments).
 - Special placeholder values like `~` or `REMOVE` can be used in lists to indicate that a key should be removed for that experiment (useful for optional settings)
- The Perturbation Cookbook (next section) provides more detailed guidance on YAML format and how values are selected per experiment.

After running the generator with the completed YAML, you will end up with the `ctrl` branch and two perturbation branches. Each perturbation branch (`perturb_1`, `perturb_2`) will contain the same changes that `ctrl` had (since they branch off `ctrl`), plus the specific parameter modifications for that experiment. Each branch will have a commit like `"Updated perturbation files: [...]"` listing the files changed for that case. You can then push these branches to your remote repository or use them for running experiments via `Payu`.

This quick start demonstrates a typical workflow: prepare YAML, run generator, then proceed with experiment runs. In practice, you might iterate on the YAML as needed to adjust parameters or add more blocks of experiments. Always use version control to your advantage – since each run configuration is a Git branch, you have a complete history of what was changed for each experiment.