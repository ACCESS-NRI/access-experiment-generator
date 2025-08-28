
# Perturbation Cookbook

This section provides additional tips and examples for writing the YAML configuration, particularly for complex cases. It covers how to format the YAML and how the `experiment-generator` interprets various inputs to assign values to each experiment.

## 1. YAML formatting guidelines
Because YAML has its own syntax rules, it's important to format the experiment plan correctly. Here are some guidelines:

### Quoting

In YAML, you generally don't need quotes around simple strings, but you do need quotes if a string contains special characters or could be misinterpreted. For example, a value like `-item` (leading dash) or `12:34 pm` (colon and space) should be quoted, otherwise YAML might think `-item` is a list item or `12:34 pm` is a key-value separator. Also, unquoted values like `yes/no`, `on/off` are interpreted as booleans or other types by YAML, so if you mean literal "yes" or "no", quote them. When in doubt, use quotes for strings, especially for any value containing `:, -, #`, or starting with special characters.

### Collections

YAML supports lists and dictionaries. Use `-` to denote list items, and `key: value` for mappings. **Indentation is significant**. For example, a list of items should be indented under a key, and a dictionary entries should be further indented. Here's a quick example:

```yaml
fruits:
  - apple
  - banana
  - cherry
settings:
  option1: true
  option2: false
```
In the first, `fruits` is a list of three strings. In the second, `settings` is a dictionary with two boolean entries. Always follow YAML indentation rules (**two spaces** is a common convention).

### Nested structures

You can nest dictionaries and lists arbitrarily. For example, you might have a dictionary that contains a list, or a list of dictionaries. Ensure the nesting in your YAML experiment plan matches the nesting of parameters in the model config files. For example, if a namelist parameter resides within a group, represent it as a nested dict under that group key (as we did with `date_manager_nml` in [YAML Guide](./Yaml-guide.md)). If a configuration file has a list of items (like a list of modules to load), you might represent it as a list in YAML.

### Some examples
 - Dict contains a list
 ```yaml
outer:
  constant: 42
  values:
    - 1
    - 2
    - 3
 ```
Here `outer` is a dict with a key `constant` and a key `values` which is a list of three numbers.

 - List of dicts
```yaml
experiments:
  - name: exp1
    param: 10
  - name: exp2
    param: 20
```
Here `experiments` is a list of two dictionaries, each with keys `name` and `param`.


## 2. How values are applied to each experiment
A crucial part of writing the perturbation section is understanding how the values you specify get mapped to each experiment branch. The generator uses a set of rules to decide, for a given YAML entry, what value goes into each experiment configuration. Below we outline these rules with examples, assuming you have defined multiple experiments.

Let's say you have three experiments (`branches`) in total for a given block: we'll call them `expt1`, `expt2`, `expt3` corresponding to indices 0, 1, 2 respectively.

 - **2.1 Scalar values (single value that is not in a list):** If you provide a plain value (e.g., `a: 5` or `mode: "x"`), that value is used for all experiments. It is effectively "broadcast" to every run. You don't need to wrap single values in a list unless you want to emphasise it's intentional. For example:

 ```yaml
 a: 10
 flag: "on"
 ```
This means every experiment gets `a=10` and `flag="on"`. If you truly need a different scalar for each experiment, you must provide a list (see below).

  - **2.2 List of values:** If you provide a list under a key, there are a few possibilities:

    - Single-element list: e.g., `b: [0.1]`. This is treated the same as a scalar value and will be given to all experiments (0.1 for all).
    - **Multi-element list (all elements identical):** e.g., `c: [5, 5, 5]` for three experiments. Since all entries are the same, this is effectively also a broadcast; each experiment will get `c=5`.
    - **Multi-element list (different elements, length == number of experiments):** e.g., for three experiments: `queue: [normal, express, normalsr]`. Here the list length matches the number of experiments, so it will assign `queue="normal"` to the first, `"express"` to the second, `"normalsr"` to the third. This is the typical way to specify distinct values per experiment.
    - **Multi-element list (length not matching number of experiments):** If you give a list of length `N` that does not equal the number of experiments (and `N > 1`, and not all identical), the generator will raise an error. This is to prevent ambiguity or accidental mis-specification.

  - **2.3 Nested dictionaries:** If the value is a dictionary, the generator will recursively apply the same logic inside that dictionary for each sub-key. Essentially, each sub-key can have its own scalar or list, and the rules apply at that level. This covers cases like nested namelist groups or config file sections.
  - **2.4 List of dictionaries:** Sometimes a configuration might have a list of similar blocks (for example, a list of components each with their own settings - `submodels` in `config.yaml` in `access-om2-configs`). If you represent this as a list of dicts in YAML, the generator will attempt to apply changes across the list. The rule it uses is: it will process each dict in the list for the given experiment index, and if all entries in that list of dicts are identical across experiments, it will treat it as no change across experiments (i.e., they remain constant). If they differ, it will keep them as a list. This is an advanced feature and in most simple cases you won't need to worry about it, but it's good to be aware that the tool can handle complex nested structures like lists of dicts.
  - **2.5 List of lists:** In some cases, your parameter might naturally be a list (e.g., a list of `modules` to load, or a list of values in a namelist). If you have a list of lists in YAML (i.e. an outer list where each item is itself a list), the generator interprets it as follows,

    - If the outer list has length 1, it assumes you meant "use this single inner list for all experiments" (broadcast the one list to all).
    - If the outer list length equals the number of experiments, it will pick the inner list at the index for each experiment.
    - Any other length will be an error (similar to the scalar list rule).

This Perturbation Cookbook is meant to serve as a reference for crafting the YAML. If your experiments aren’t behaving as expected, double-check the YAML format against these rules. Additionally, the tool will warn or error out in many cases where the input is ambiguous or inconsistent (for example, if you forgot to provide the `branches` key in a block, it will warn and skip that block).

With a correctly prepared YAML, the `experiment-generator` will handle the heavy lifting of repository cloning, branch management, and file editing, allowing you to focus on analyzing the outcomes of your model experiments.