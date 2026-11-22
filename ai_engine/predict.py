
import joblib
import os

from datetime import datetime


# --------------------------------------------------
# MODEL CONFIGURATION
# --------------------------------------------------

MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "food_demand_model.pkl"
)

_model = None


# --------------------------------------------------
# LOAD AI MODEL
# --------------------------------------------------

def load_demand_model():

    global _model

    if _model is not None:
        return _model

    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            "AI model not found. Run train_model.py first."
        )

    _model = joblib.load(MODEL_PATH)

    return _model


# --------------------------------------------------
# FOOD CATEGORY ENCODING
# Must match train_model.py
# --------------------------------------------------

def encode_food_category(food_category):

    categories = {
        "cooked meals": 0,
        "fruits": 1,
        "vegetables": 2
    }

    category = str(food_category).strip().lower()

    if category not in categories:
        raise ValueError(
            f"Unsupported food category: {food_category}. "
            "Supported categories: Cooked Meals, Fruits, Vegetables."
        )

    return categories[category]


# --------------------------------------------------
# FOOD DEMAND PREDICTION
# --------------------------------------------------

def predict_food_demand(
    hour,
    day_of_week,
    food_category,
    quantity_kg
):

    hour = int(hour)
    day_of_week = int(day_of_week)
    quantity_kg = float(quantity_kg)

    if not 0 <= hour <= 23:
        raise ValueError(
            "Hour must be between 0 and 23."
        )

    if not 0 <= day_of_week <= 6:
        raise ValueError(
            "Day of week must be between 0 and 6."
        )

    if quantity_kg <= 0:
        raise ValueError(
            "Food quantity must be greater than zero."
        )

    category_code = encode_food_category(
        food_category
    )

    model = load_demand_model()

    prediction = model.predict([[
        hour,
        day_of_week,
        category_code,
        quantity_kg
    ]])[0]

    prediction = max(
        0,
        min(float(prediction), quantity_kg)
    )

    surplus = max(
        0,
        quantity_kg - prediction
    )

    surplus_percentage = (
        (surplus / quantity_kg) * 100
    )

    return {
        "predicted_demand_kg": round(
            prediction, 2
        ),
        "surplus_kg": round(
            surplus, 2
        ),
        "surplus_percentage": round(
            surplus_percentage, 2
        )
    }


# --------------------------------------------------
# DONATION URGENCY SCORING
# --------------------------------------------------

def calculate_urgency_score(
    expiry_at,
    quantity_kg,
    predicted_demand_kg=None
):

    if not isinstance(expiry_at, datetime):
        raise ValueError(
            "expiry_at must be a Python datetime object."
        )

    quantity_kg = float(quantity_kg)

    if quantity_kg <= 0:
        raise ValueError(
            "Food quantity must be greater than zero."
        )

    current_time = datetime.now(
        expiry_at.tzinfo
    )

    remaining_hours = (
        expiry_at - current_time
    ).total_seconds() / 3600

    # Base urgency based on expiry time
    if remaining_hours <= 0:
        urgency_score = 100

    elif remaining_hours <= 2:
        urgency_score = 90

    elif remaining_hours <= 6:
        urgency_score = 75

    elif remaining_hours <= 12:
        urgency_score = 60

    elif remaining_hours <= 24:
        urgency_score = 45

    elif remaining_hours <= 48:
        urgency_score = 30

    else:
        urgency_score = 15

    surplus_kg = 0
    surplus_percentage = 0

    # Adjust urgency based on predicted surplus
    if predicted_demand_kg is not None:

        predicted_demand_kg = float(
            predicted_demand_kg
        )

        if predicted_demand_kg < 0:
            raise ValueError(
                "Predicted demand cannot be negative."
            )

        predicted_demand_kg = min(
            predicted_demand_kg,
            quantity_kg
        )

        surplus_kg = max(
            0,
            quantity_kg - predicted_demand_kg
        )

        surplus_percentage = (
            surplus_kg / quantity_kg
        ) * 100

        if surplus_percentage >= 75:
            urgency_score += 10

        elif surplus_percentage >= 50:
            urgency_score += 7

        elif surplus_percentage >= 25:
            urgency_score += 4

    # Keep score between 0 and 100
    urgency_score = min(
        100,
        max(0, urgency_score)
    )

    # Determine urgency level
    if urgency_score >= 80:
        urgency_level = "Critical"

    elif urgency_score >= 60:
        urgency_level = "High"

    elif urgency_score >= 35:
        urgency_level = "Medium"

    else:
        urgency_level = "Low"

    return {
        "urgency_score": urgency_score,
        "urgency_level": urgency_level,
        "remaining_hours": round(
            max(0, remaining_hours), 2
        ),
        "surplus_kg": round(
            surplus_kg, 2
        ),
        "surplus_percentage": round(
            surplus_percentage, 2
        )
    }


# --------------------------------------------------
# COMPLETE FOOD AI ANALYSIS
# --------------------------------------------------

def analyze_food_donation(
    expiry_at,
    quantity_kg,
    food_category,
    hour=None,
    day_of_week=None
):

    current_time = datetime.now()

    if hour is None:
        hour = current_time.hour

    if day_of_week is None:
        day_of_week = current_time.weekday()

    # Predict food demand
    demand_result = predict_food_demand(
        hour=hour,
        day_of_week=day_of_week,
        food_category=food_category,
        quantity_kg=quantity_kg
    )

    # Calculate urgency using predicted demand
    urgency_result = calculate_urgency_score(
        expiry_at=expiry_at,
        quantity_kg=quantity_kg,
        predicted_demand_kg=demand_result[
            "predicted_demand_kg"
        ]
    )

    return {
        "predicted_demand_kg":
            demand_result["predicted_demand_kg"],

        "surplus_kg":
            demand_result["surplus_kg"],

        "surplus_percentage":
            demand_result["surplus_percentage"],

        "urgency_score":
            urgency_result["urgency_score"],

        "urgency_level":
            urgency_result["urgency_level"],

        "remaining_hours":
            urgency_result["remaining_hours"]
    }
