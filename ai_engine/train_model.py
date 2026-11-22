
import os
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
import joblib

# Create realistic demonstration training data
data = {
    "hour": [8, 12, 14, 18, 20, 9, 13, 17, 21, 11, 15, 19, 7, 16, 22],
    "day_of_week": [0, 1, 2, 3, 4, 5, 6, 0, 1, 2, 3, 4, 5, 6, 0],
    "food_category": [0, 1, 2, 0, 1, 2, 0, 1, 2, 0, 1, 2, 0, 1, 2],
    "quantity_kg": [5, 20, 12, 30, 15, 8, 25, 18, 10, 22, 14, 28, 6, 16, 24],
    "demand_kg": [4, 18, 10, 25, 12, 7, 20, 16, 8, 19, 12, 23, 5, 14, 20]
}

df = pd.DataFrame(data)

X = df[["hour", "day_of_week", "food_category", "quantity_kg"]]
y = df["demand_kg"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

predictions = model.predict(X_test)

print("Model training completed!")
print("MAE:", mean_absolute_error(y_test, predictions))
print("R2 score:", r2_score(y_test, predictions))

os.makedirs("ai_engine", exist_ok=True)
joblib.dump(model, "ai_engine/food_demand_model.pkl")

print("Model saved to ai_engine/food_demand_model.pkl")
