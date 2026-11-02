import pandas as pd
from sklearn.linear_model import LinearRegression
import pickle

data = pd.read_csv("dataset/crop_data.csv")

X = data[['temperature', 'rainfall', 'humidity']]
y = data['yield']

model = LinearRegression()
model.fit(X, y)

pickle.dump(model, open("models/yield_model.pkl", "wb"))

print("Model Trained Successfully!")