---
name: jupyter-headless
description: Run a Jupyter notebook (.ipynb) from the command line without a browser and get its outputs as text. Use when the paper's results come from a notebook.
---

# Notebooks without a browser

A notebook's saved outputs are from the author's session. They don't count as this run's
output, and cells may have been run out of order. Run it again from the top.

## Run the whole notebook

Install the tools into the same virtual environment as the paper's packages:

```
.venv/bin/pip install nbconvert nbclient ipykernel
cd repo && ../.venv/bin/jupyter nbconvert --to notebook --execute analysis.ipynb \
  --output ../analysis.executed.ipynb --ExecutePreprocessor.timeout=600
```

- Write the executed copy outside the repository, as above, so the original stays unchanged.
- This is the experiment, so run it through `run_experiment`.
- The first failing cell stops the run and prints its traceback. `--allow-errors` keeps going,
  which helps to see every failure at once but can produce numbers from a half-broken state.
  Don't take answers from a run that used it.

## Get the outputs as text

The executed notebook is JSON, so the numbers aren't in the command's printed output yet.
Print them, so they land in the saved log where evidence has to come from:

```
.venv/bin/python - <<'EOF'
import json
nb = json.load(open("analysis.executed.ipynb"))
for i, cell in enumerate(nb["cells"]):
    for out in cell.get("outputs", []):
        text = out.get("text") or out.get("data", {}).get("text/plain") or []
        if text:
            print(f"--- cell {i}")
            print("".join(text))
EOF
```

## Common problems

- **Kernel not found:** the notebook names the author's kernel. Add
  `--ExecutePreprocessor.kernel_name=python3`.
- **Paths:** notebooks read data relative to where they were started. Run from the notebook's
  own folder first.
- **Magics and shell lines** (`%matplotlib inline`, `!pip install ...`): they run under
  nbconvert. A `!pip install` inside the notebook installs into whatever Python the kernel
  uses, which may not be the virtual environment; install those packages yourself first.
- **Answers in a plot:** the value has to be printed to count as evidence. If it only exists
  as a figure, say so and record it as an obstacle (stage "extract").
