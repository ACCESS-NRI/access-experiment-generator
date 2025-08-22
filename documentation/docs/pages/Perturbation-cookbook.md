### Some notes on the yaml format
In the yaml input, you can write a string without quotes if it doesn’t contain “problematic” characters (like :, #, {}, [], ,, quotes themselves, etc.).

You only need quotes if:

- The string starts with special characters (:, -, ?, #, *, &, %, @, !, etc.).
- The string contains : followed by a space (YAML would think it’s a key–value separator).
- The string is coincident with magic keywords.
- You want to include newlines or preserve leading/trailing spaces.

Some examples could be
```yaml
a: -item # yaml treats -item as a list
b: "-item" # this is correct
```

```yaml
a: 12:34 pm # yaml thinks ":" starts a new mapping
b: "12:34 pm" # this is correct
```

```yaml
a: "hello\nworld" # this preserves new lines
b: "  hello world  " # this preserves spacings
```

```yaml
# coincident with magic keywords
a: yes # yaml interpretes this as True
b: no # yaml interpretes this as False
c: null # None
d: ~ # None
...
```

## Some background
- Assume we have three perturbation experiments - `total_exps = 3`
- Three experiments, `index = 0,1,2`

### 1. Scalar (numbers/strings)
```yaml
# yaml
a: 1
b: x
```

```python3
# python
data = {"a": 1, b: "x"}
# Then data (`a` and `b`) is broadcasted to all the three perturbation configurations.
```

### 2. Nested dict
```yaml
# yaml
outer:
  a: 10
  b: [1, 2, 3]
```

```python3
# python
data = {"outer": {"a": 10, "b": [1, 2, 3]}}
# `a` will be broadcasted to all configurations; `b=1` when index=0, similar to the other 2 configurations
```

### 3. Plain lists
#### 3.1 single-element list
```yaml
# yaml
a: [1]
b: [x]
```

```python3
# python
data = {"a": [1], "b": [x]}
# Then data (`a` and `b`) is broadcasted to all the three perturbation configurations.
```
