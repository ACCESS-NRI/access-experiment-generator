# Experiment Generator

The **ACCESS Experiment Generator** is a command-line tool for automatically creating one or more experiment configurations from a base "control" experiment. Its primary goal is to reduce manual editing and ensure consistent, repeatable workflows, especially when generating large ensembles of perturbation experiments. By defining a set of parameter changes in a single YAML configuration file, users can produce multiple experiment variants in one go, rather than setting up each experiment by hand. This helps researchers efficiently explore model sensitivities, quantify uncertainties, and test robustness across different parameter settings. Each experiment variant is version-controlled in Git, making it easy to track changes and reproduce results.

Get **ACCESS-experiment-generator** from the [Github Repository](https://github.com/ACCESS-NRI/access-experiment-generator).

## Why perturbation experiments?

Climate models contain thousands of uncertain parameters. Systematically varying them helps you:

- **Sensitivity** — vary parameters systematically
- **Uncertainty** — build ensembles instead of one-offs
- **Reproducibility** — same inputs -> same branches
- **Provenance** — every variant lives on its own Git branch

## Key features

### 1. YAML-driven configuration
Users specify a suite of parameter changes in a single YAML file (the "experiment plan"). Each set of changes corresponds to a new experiment variant. The generator reads this YAML input and applies the specified changes to the model configuration files automatically. 

### 2. Git branch per experiment

The generator uses a branch-based workflow to keep experiments isolated. Starting from a given control setup (on a base branch or commit), it creates a new Git branch for each perturbation experiment, applies the parameter changes on that branch, and commits the changes. 

### 3. Integration with [`Payu`](https://github.com/payu-org/payu)

The tool is designed to fit into the ACCESS modeling workflow and works with the `Payu` system for running models on HPC. The generator prepares experiment configurations (on systems like Gadi, NCI) that are ready to run with Payu, although actually running the experiments is outside the generator’s scope. There is a companion simple tool – [**access-experiment-runner**](https://github.com/ACCESS-NRI/access-experiment-runner) is specifically used for submitting and running jobs.


## Quick Guide

```bash
# On Gadi
module use /g/data/vk83/prerelease/modules && module load payu/dev
# or: python -m venv .venv && source .venv/bin/activate && pip install experiment-generator

# Generate experiments from YAML
experiment-generator -i Experiment_generator.yaml
```