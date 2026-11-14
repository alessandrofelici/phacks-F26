# CORE-Bench task triage (Role B)

Read from the capsules' files on 2026-11-14. **Nothing here has been run yet**, so "should be quick" is a judgment from the code and dependencies, not a measurement. Get them with:

```
python -m harness.corebench fetch 6460826 4098236 --level medium
python -m harness.corebench fetch 6460826 4098236 --level hard
```

## Picks for the MVP

| Capsule | Paper | Why | Watch out for |
|---|---|---|---|
| **6460826** | CULP: Classification Using Link Prediction | CPU only, three short scripts, tiny data (Iris from scikit-learn, two text files), 6 numeric answers | Pins from 2018 (Python 3.6, networkx 2.1, pandas 0.23, scikit-learn 0.19), so the agent has to deal with old versions. Reads `/data/wine.txt` by absolute path |
| **4098236** | Multi-Label Classification via ART-Based Clustering | CPU only, one script, numpy/scikit-learn/scikit-multilearn, 2 numeric answers | No data folder: it downloads its dataset with `skmultilearn.dataset.load_dataset`, so it needs network. Uses `n_jobs=-1` cross-validation |

Use **medium** (Dockerfile and run script kept) for checkpoint 2, then **hard** (both removed) once medium works.

## Backups

| Capsule | Paper | Notes |
|---|---|---|
| 2011424 | Mining Emerging Fuzzy-Temporal Gradual Patterns | Light dependencies (numpy, scikit-fuzzy), 1 answer. **The capsule ships the authors' output in `code/results/output.txt`, which contains the answer.** The loader now removes nested `results` folders at medium and hard |
| 0940461 | WABL Method as a Universal Defuzzifier | Runs a notebook with `jupyter nbconvert`; needs the Anaconda stack |
| 5975162 | ExPSO Package | The script is a plain optimizer, but the listed environment installs TensorFlow and PyTorch |

## Skip for now

| Capsule | Why |
|---|---|
| 0238624 | Needs `tensorflow-gpu` 2.4.1 and loads saved `.h5` models |
| 5286757 | Trains a PyTorch 1.2 model for 10 epochs |
| 3269870 | TensorFlow 1.4 on Python 2.7, plus a question about a plot |
