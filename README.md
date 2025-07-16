# access-experiment-generator

[![CI](https://github.com/ACCESS-NRI/access-experiment-generator/actions/workflows/ci.yml/badge.svg)](https://github.com/ACCESS-NRI/access-experiment-generator/actions/workflows/ci.yml)
[![Coverage Status](https://codecov.io/gh/ACCESS-NRI/access-experiment-generator/branch/main/graph/badge.svg)](https://codecov.io/gh/ACCESS-NRI/access-experiment-generator)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue?style=flat-square)](https://opensource.org/license/apache-2-0) 
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)


# About
The main role of the ACCESS experiment generator is to streamline the creation of one or more experiment configurations from a "control" experiment setup. It reduces manual editing and ensures consistent, repeatable workflows for large ensembles. 

# Key features
1. Parameter perturbation / Configuration changes
    - Users provide a set or suite of parameter changes in a YAML input file.
    - The generator applies these changes to relevant configurations.
    - It can generate multiple experiments automatically, making it especially useful for large perturbation ensembles.

2. Branch-based storage approach
    - The generator checks out a control branch in a git repository.
    - For each perturbation, it creates a new branch containing modified parameters.
    - Changes are then committed on that branch and can be pushed back to the github repository.
