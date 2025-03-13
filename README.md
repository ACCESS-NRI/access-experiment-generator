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
