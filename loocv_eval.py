import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error
from model import GrassdayModel, load_training_data
import demo

# Seed demo data first if not present
demo.seed_demo_data()

X, y = load_training_data()

if len(X) < 2:
    print("Not enough data.")
    exit()

# Naive baseline: predicting mean of training set
naive_predictions = []
loocv_predictions = []

for i in range(len(X)):
    # Leave one out
    X_train = X.drop(X.index[i])
    y_train = y.drop(y.index[i])
    X_test = X.iloc[[i]]
    y_true = y.iloc[i]
    
    # Naive baseline
    naive_pred = y_train.mean()
    naive_predictions.append(naive_pred)
    
    # Model baseline
    clf = GrassdayModel(device="cpu")
    clf.fit(X_train, y_train)
    
    # Predict using GrassdayModel's blended method
    # Since we are evaluating the model's pure capability against synthetic preference,
    # and train_count will be large, predict_window works fine.
    pred_dict = clf.predict_window(X_test.iloc[0])
    loocv_predictions.append(pred_dict["q50"])

naive_mae = mean_absolute_error(y, naive_predictions)
model_mae = mean_absolute_error(y, loocv_predictions)

print(f"LOOCV Evaluation on {len(X)} synthetic outings:")
print(f"Naive Baseline MAE: {naive_mae:.2f}")
print(f"TabPFN Model MAE: {model_mae:.2f}")
print(f"Improvement: {(naive_mae - model_mae) / naive_mae * 100:.1f}%")
