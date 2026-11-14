# Toy linear regression

Code for the (fictional) note "Weak ridge beats OLS when samples are scarce".

## Reproduce

```
pip install -r requirements.txt
python run.py --seed 0
```

The script prints the validation R^2 of three candidates (ols, ridge-weak,
ridge-strong), the selected model, and its test R^2.
