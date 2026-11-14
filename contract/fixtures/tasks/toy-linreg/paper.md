# Weak ridge beats OLS when samples are scarce (toy note)

We fit a 40-feature linear model on 60 training samples and choose between
ordinary least squares and two ridge penalties using a validation split.
With seed 0, the weak ridge penalty is selected and reaches a test R^2 of 0.46.
