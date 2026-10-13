The project is organised with the following components,

```
.
├── conda                                 # conda environment
│   ├── environment.yml
│   └── meta.yaml
├── COPYRIGHT.txt
├── examples
│   └── Experiment_generator_example.yaml # An example YAML
├── LICENSE
├── pyproject.toml                        # package metadata, deps, console_scripts
├── README.md
├── setup.py                              # conda recipe versioning
├── src                                 
│   └── experiment_generator              # source code
│       ├── base_experiment.py            # Common path+repo config helpers
│       ├── config_file_updater.py        # The updater: edits every config file in place, with the access-config-utils parsers
│       ├── experiment_generator.py       # Orchestrator (end-to-end flow)
│       ├── main.py                       # CLI entrypoint - loads YAML, runs Orchestrator
│       ├── perturbation_experiment.py    # Houses control/perturbation setups
│       └── utils.py                      # Helpers
├── .github/workflows/                    # CI/CD
└── tests                                 # Unittests suite

6 directories, 35 files
```

Some major components are explained a bit as follows,

- `base_experiment.py`: A helper base class that parses general settings from the input dictionary and provides common attributes (such as paths and repository info) used by both control and perturbation workflows.
- `experiment_generator.py`: The high-level orchestrator that sets up the experiments. It inherits from `BaseExperiment` and coordinates the overall workflow.
- `perturbation_experiment.py`: Manages the creation of the control experiment and all perturbation experiments. This class extends `BaseExperiment`, so it has access to the same configuration attributes. It provides methods like `manage_control_expt()` for applying parameter updates to the control branch, and `manage_perturb_expt()` for looping through each defined perturbation, creating branches and applying changes.
   - Inside it, there is a simple data structure (`ExperimentDefinition`) that represents each perturbation experiment definition. Each instance holds,
      1. block name (a label/group from the YAML, e.g. `Parameter_block1`), 
      2. target branch name for that experiment, 
      3. a dict of file parameters to change. 

   - The generator flattens the nested YAML definitions into a list of `ExperimentDefinition` objects, each corresponding to one experiment case, before actually creating branches and applying changes.
- `config_file_updater.py`: Applies the changes to a configuration file. The files are read with the round-trip parsers from [access-config-utils](https://github.com/ACCESS-NRI/access-config-utils), which keep comments and formatting, so only the lines that change are touched. Every parser hands the file over as a dictionary, so one updater serves all of them: it parses the file, merges the changes from the YAML input into it, and writes it back. The few files that need more (`jobname` in `config.yaml`, `turning_angle` in CICE namelists, the fields of `forcing.json`) have a small hook that runs before the merge.
