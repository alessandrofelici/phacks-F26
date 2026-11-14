"""Toy 'paper': model selection for linear regression on synthetic data.

Usage: python run.py --seed 0
Prints the validation score of each candidate, the selected model and its
test R^2. Everything is closed-form, so it runs in about a second.
"""
import argparse

import numpy as np

CANDIDATES = {"ols": 0.0, "ridge-weak": 5.0, "ridge-strong": 200.0}


def make_data(seed, n=240, d=40):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, d))
    w = np.zeros(d)
    w[:8] = rng.normal(scale=2.0, size=8)
    y = X @ w + rng.normal(scale=2.5, size=n)
    return X, y


def fit(X, y, alpha):
    d = X.shape[1]
    return np.linalg.solve(X.T @ X + alpha * np.eye(d), X.T @ y)


def r2(X, y, w):
    resid = y - X @ w
    return 1.0 - float(resid @ resid) / float(((y - y.mean()) ** 2).sum())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    X, y = make_data(args.seed)
    X_train, y_train = X[:60], y[:60]
    X_val, y_val = X[60:140], y[60:140]
    X_test, y_test = X[140:], y[140:]

    best_name, best_val = None, -np.inf
    for name, alpha in CANDIDATES.items():
        w = fit(X_train, y_train, alpha)
        val = r2(X_val, y_val, w)
        print(f"val r2 [{name}]: {val:.4f}")
        if val > best_val:
            best_name, best_val = name, val

    w = fit(X_train, y_train, CANDIDATES[best_name])
    print(f"best model: {best_name}")
    print(f"test r2: {r2(X_test, y_test, w):.4f}")


if __name__ == "__main__":
    main()
