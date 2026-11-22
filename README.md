# FoodRescue AI 🍃
### AI-Powered Food Waste Management and Redistribution System

## About the Project

FoodRescue AI is a web-based application that uses Artificial Intelligence and Machine Learning to help reduce edible food waste.

The platform connects food donors with NGOs and helps coordinate food donation, collection and delivery through an intelligent centralized system.

## Problem Statement

Large quantities of edible food are wasted every day, while many people face food insecurity. Traditional donation processes often lack efficient coordination between food donors and organizations.

FoodRescue AI aims to address this problem through an AI-powered food redistribution platform.

## Objectives

- Reduce edible food wastage.
- Connect food donors with NGOs.
- Predict food demand using machine learning.
- Identify surplus food and donation urgency.
- Recommend suitable NGOs.
- Manage food donations and deliveries.
- Provide administrative monitoring and analytics.

## Key Features

- User registration and login with OTP verification.
- Role-based dashboards for Donors, NGOs, Delivery Partners and Administrators.
- Food donation creation and management.
- Machine learning-based food demand prediction.
- Surplus food estimation and urgency calculation.
- Intelligent NGO matching based on distance, category and capacity.
- Donation claiming and delivery management.
- Delivery partner assignment and status updates.
- Email and in-app notifications.
- Admin dashboard and analytics.

## Technologies Used

**Programming Language**
- Python

**Frontend**
- HTML5
- CSS3
- JavaScript

**Backend**
- Flask
- Flask-Login
- Flask-SQLAlchemy

**AI and Machine Learning**
- Scikit-learn
- Random Forest Regression
- NumPy
- Pandas
- Joblib

**Database**
- SQLite
- SQLAlchemy

**Other Tools**
- Visual Studio Code
- Chart.js
- Leaflet Maps
- Gmail SMTP

## Machine Learning Methodology

The project uses a Random Forest Regression model to predict food demand based on:

- Hour of the day
- Day of the week
- Food category
- Available food quantity

The predicted demand is used to estimate surplus food and calculate donation urgency.

An NGO matching algorithm recommends suitable organizations using geographical distance, food preferences and handling capacity.

**Note:** The current model is a prototype trained using synthetic demonstration data. Real-world datasets and further validation are required for practical deployment.

## Project Structure

```text
FoodRescue_AI/
│
├── ai_engine/
│   ├── food_demand_model.pkl
│   ├── ngo_matching.py
│   ├── predict.py
│   └── train_model.py
│
├── static/
│   └── css/
│       └── style.css
│
├── templates/
│
├── app.py
├── auth.py
├── models.py
├── extensions.py
├── create_admin.py
├── requirements.txt
└── README.md
```

## Running the Project Locally

1. Clone the repository:

```bash
git clone https://github.com/harshavardhanpolakala-ops/FoodRescue-AI.git
```

2. Open the project directory:

```bash
cd FoodRescue-AI
```

3. Create and activate a Python virtual environment.

4. Install dependencies:

```bash
pip install -r requirements.txt
```

5. Configure the required environment variables in a local `.env` file.

6. Start the application:

```bash
python app.py
```

7. Open the application in your browser:

```text
http://127.0.0.1:5000
```

## Future Scope

- Integration with real-world food donation datasets.
- Improved machine learning prediction accuracy.
- Live GPS-based delivery tracking.
- Mobile application development.
- Integration with more NGOs and food donation organizations.
- Cloud deployment and scalability.

## Conclusion

FoodRescue AI demonstrates how Artificial Intelligence, Machine Learning and web technologies can be combined to address food wastage and improve food redistribution.

The project provides a foundation for a smarter and more efficient food donation ecosystem.

**Turning surplus food into an opportunity to feed people in need.**
