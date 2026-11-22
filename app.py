
import os
import math
import smtplib

from datetime import datetime
from email.message import EmailMessage

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import (
    LoginManager,
    login_required,
    current_user,
    logout_user
)
from dotenv import load_dotenv
from sqlalchemy import inspect, text

from extensions import db
from ai_engine.ngo_matching import match_ngos
from ai_engine.predict import analyze_food_donation


# ==================================================
# APPLICATION CONFIGURATION
# ==================================================

load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "foodrescue-development-key"
)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///foodrescue.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["MAIL_SERVER"] = os.getenv(
    "MAIL_SERVER",
    "smtp.gmail.com"
)

app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", 587))

app.config["MAIL_USE_TLS"] = (
    os.getenv("MAIL_USE_TLS", "True").lower() == "true"
)

app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")

app.config["MAIL_DEFAULT_SENDER"] = os.getenv(
    "MAIL_DEFAULT_SENDER"
)


# ==================================================
# EMAIL NOTIFICATION SYSTEM
# ==================================================

def send_notification_email(recipient, subject, message):

    if not recipient:
        print("EMAIL NOTIFICATION SKIPPED: No recipient.")
        return False

    mail_username = app.config.get("MAIL_USERNAME")
    mail_password = app.config.get("MAIL_PASSWORD")

    sender = (
        app.config.get("MAIL_DEFAULT_SENDER")
        or mail_username
    )

    if not mail_username or not mail_password or not sender:

        print("EMAIL ERROR: Gmail SMTP configuration is incomplete.")
        return False

    email_message = EmailMessage()

    email_message["Subject"] = subject
    email_message["From"] = sender
    email_message["To"] = recipient

    email_message.set_content(message)

    try:

        with smtplib.SMTP(
            app.config["MAIL_SERVER"],
            app.config["MAIL_PORT"],
            timeout=15
        ) as server:

            if app.config["MAIL_USE_TLS"]:
                server.starttls()

            server.login(
                mail_username,
                mail_password
            )

            server.send_message(email_message)

        print("EMAIL SENT SUCCESSFULLY:", recipient)

        return True

    except Exception as error:

        print("EMAIL NOTIFICATION ERROR:", error)

        return False


# ==================================================
# DATABASE INITIALIZATION
# ==================================================

db.init_app(app)


# ==================================================
# LOGIN MANAGER
# ==================================================

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"

from models import (
    User,
    FoodDonation,
    Delivery,
    DonationClaim,
    Notification
)

from auth import auth

app.register_blueprint(auth)


@login_manager.user_loader
def load_user(user_id):

    try:
        return db.session.get(User, int(user_id))

    except (ValueError, TypeError):
        return None


# ==================================================
# IN-APP NOTIFICATION HELPER
# ==================================================

def create_notification(
    user_id,
    title,
    message,
    notification_type="General",
    donation_id=None
):

    try:

        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            donation_id=donation_id,
            is_read=False
        )

        db.session.add(notification)
        db.session.commit()

        return True

    except Exception as error:

        db.session.rollback()

        print("IN-APP NOTIFICATION ERROR:", error)

        return False


# ==================================================
# GLOBAL UNREAD NOTIFICATION COUNT
# ==================================================

@app.context_processor
def inject_notification_count():

    unread_count = 0

    if current_user.is_authenticated:

        unread_count = Notification.query.filter_by(
            user_id=current_user.id,
            is_read=False
        ).count()

    return {
        "unread_notification_count": unread_count
    }


# ==================================================
# BLOCK DEACTIVATED ACCOUNTS
# ==================================================

@app.before_request
def check_account_status():

    if current_user.is_authenticated:

        if not current_user.is_active:

            logout_user()

            flash(
                "Your account has been deactivated. "
                "Please contact the administrator.",
                "error"
            )

            return redirect(url_for("auth.login"))


# ==================================================
# ACCESS CONTROL
# ==================================================

def admin_required():

    if current_user.role != "Admin":

        flash(
            "Administrator access required.",
            "error"
        )

        return False

    return True


def role_required(*allowed_roles):

    if current_user.role not in allowed_roles:

        flash(
            "You do not have permission to access this page.",
            "error"
        )

        return False

    return True


# ==================================================
# HOME PAGE
# ==================================================

@app.route("/")
def home():

    return render_template("index.html")


# ==================================================
# ROLE-BASED DASHBOARD
# ==================================================

@app.route("/dashboard")
@login_required
def dashboard():

    if current_user.role == "Admin":
        return redirect(url_for("admin_dashboard"))

    dashboard_data = {}

    if current_user.role == "Donor":

        donations = FoodDonation.query.filter_by(
            donor_id=current_user.id
        ).all()

        dashboard_data = {
            "total_donations": len(donations),

            "total_quantity": round(
                sum(d.quantity_kg or 0 for d in donations),
                2
            ),

            "active_donations": sum(
                1 for d in donations
                if d.status == "Available"
            ),

            "claimed_donations": sum(
                1 for d in donations
                if d.status == "Claimed"
            ),

            "completed_donations": sum(
                1 for d in donations
                if d.status == "Completed"
            )
        }

    elif current_user.role == "NGO":

        claims = DonationClaim.query.filter_by(
            ngo_id=current_user.id
        ).all()

        dashboard_data = {
            "total_claims": len(claims),

            "total_quantity": round(
                sum(
                    c.donation.quantity_kg
                    for c in claims
                    if c.donation
                ),
                2
            ),

            "active_claims": sum(
                1 for c in claims
                if c.donation
                and c.donation.status == "Claimed"
            ),

            "completed_claims": sum(
                1 for c in claims
                if c.donation
                and c.donation.status == "Completed"
            )
        }

    elif current_user.role == "Delivery Partner":

        deliveries = Delivery.query.filter_by(
            delivery_partner_id=current_user.id
        ).all()

        dashboard_data = {
            "total_deliveries": len(deliveries),

            "pending_deliveries": sum(
                1 for d in deliveries
                if d.status in [
                    "Requested",
                    "Pending",
                    "Assigned",
                    "Picked Up",
                    "In Transit"
                ]
            ),

            "completed_deliveries": sum(
                1 for d in deliveries
                if d.status == "Delivered"
            )
        }

    else:

        flash(
            "Your account role is not recognized.",
            "error"
        )

        return redirect(url_for("auth.logout"))

    return render_template(
        "dashboard.html",
        dashboard_data=dashboard_data
    )


# ==================================================
# ADMIN CONTROL CENTER
# ==================================================

@app.route("/admin")
@login_required
def admin_dashboard():

    if not admin_required():
        return redirect(url_for("dashboard"))

    users = User.query.order_by(
        User.created_at.desc()
    ).all()

    donations = FoodDonation.query.order_by(
        FoodDonation.created_at.desc()
    ).all()

    deliveries = Delivery.query.order_by(
        Delivery.created_at.desc()
    ).all()

    delivery_partners = User.query.filter_by(
        role="Delivery Partner",
        is_active=True
    ).order_by(
        User.created_at.desc()
    ).all()

    total_users = len(users)

    active_users = sum(
        1 for user in users if user.is_active
    )

    inactive_users = sum(
        1 for user in users if not user.is_active
    )

    total_donations = len(donations)

    total_food_rescued = sum(
        donation.quantity_kg or 0
        for donation in donations
        if donation.status == "Completed"
    )

    available_donations = sum(
        1 for donation in donations
        if donation.status == "Available"
    )

    claimed_donations = sum(
        1 for donation in donations
        if donation.status == "Claimed"
    )

    completed_donations = sum(
        1 for donation in donations
        if donation.status == "Completed"
    )

    requested_deliveries = sum(
        1 for delivery in deliveries
        if delivery.status == "Requested"
    )

    active_deliveries = sum(
        1 for delivery in deliveries
        if delivery.status in [
            "Assigned",
            "Picked Up",
            "In Transit"
        ]
    )

    completed_deliveries = sum(
        1 for delivery in deliveries
        if delivery.status == "Delivered"
    )

    return render_template(
        "admin_dashboard.html",
        users=users,
        donations=donations,
        deliveries=deliveries,
        delivery_partners=delivery_partners,
        total_users=total_users,
        active_users=active_users,
        inactive_users=inactive_users,
        total_donations=total_donations,
        total_food_rescued=round(total_food_rescued, 2),
        available_donations=available_donations,
        claimed_donations=claimed_donations,
        completed_donations=completed_donations,
        requested_deliveries=requested_deliveries,
        active_deliveries=active_deliveries,
        completed_deliveries=completed_deliveries
    )


# ==================================================
# ADMIN: CHANGE USER ROLE
# ==================================================

@app.route(
    "/admin/update-user-role/<int:user_id>",
    methods=["POST"]
)
@login_required
def admin_update_user_role(user_id):

    if not admin_required():
        return redirect(url_for("dashboard"))

    user = db.session.get(User, user_id)

    if not user:

        flash("User not found.", "error")
        return redirect(url_for("admin_dashboard"))

    if user.id == current_user.id:

        flash(
            "You cannot change your own account role.",
            "error"
        )

        return redirect(url_for("admin_dashboard"))

    if user.role == "Admin":

        flash(
            "Admin account roles cannot be changed here.",
            "error"
        )

        return redirect(url_for("admin_dashboard"))

    new_role = request.form.get(
        "role",
        ""
    ).strip()

    allowed_roles = [
        "Donor",
        "NGO",
        "Delivery Partner"
    ]

    if new_role not in allowed_roles:

        flash("Please select a valid user role.", "error")
        return redirect(url_for("admin_dashboard"))

    try:

        user.role = new_role

        db.session.commit()

        flash(
            f"{user.name}'s role was updated to {new_role}.",
            "success"
        )

    except Exception as error:

        db.session.rollback()

        print("USER ROLE UPDATE ERROR:", error)

        flash(
            "Unable to update the user role.",
            "error"
        )

    return redirect(url_for("admin_dashboard"))


# ==================================================
# ADMIN: ACTIVATE / DEACTIVATE USER
# ==================================================

@app.route(
    "/admin/toggle-user-status/<int:user_id>",
    methods=["POST"]
)
@login_required
def admin_toggle_user_status(user_id):

    if not admin_required():
        return redirect(url_for("dashboard"))

    user = db.session.get(User, user_id)

    if not user:

        flash("User not found.", "error")
        return redirect(url_for("admin_dashboard"))

    if user.id == current_user.id:

        flash(
            "You cannot deactivate your own account.",
            "error"
        )

        return redirect(url_for("admin_dashboard"))

    if user.role == "Admin":

        flash(
            "Admin accounts cannot be deactivated through this page.",
            "error"
        )

        return redirect(url_for("admin_dashboard"))

    try:

        user.is_active = not user.is_active

        new_status = (
            "activated" if user.is_active else "deactivated"
        )

        db.session.commit()

        flash(
            f"{user.name}'s account has been {new_status}.",
            "success"
        )

    except Exception as error:

        db.session.rollback()

        print("USER STATUS UPDATE ERROR:", error)

        flash(
            "Unable to update account status.",
            "error"
        )

    return redirect(url_for("admin_dashboard"))


# ==================================================
# ADMIN: DELETE USER
# ==================================================

@app.route(
    "/admin/delete-user/<int:user_id>",
    methods=["POST"]
)
@login_required
def admin_delete_user(user_id):

    if not admin_required():
        return redirect(url_for("dashboard"))

    user = db.session.get(User, user_id)

    if not user:

        flash("User not found.", "error")
        return redirect(url_for("admin_dashboard"))

    if user.id == current_user.id:

        flash(
            "You cannot delete your own Admin account.",
            "error"
        )

        return redirect(url_for("admin_dashboard"))

    if user.role == "Admin":

        flash(
            "Admin accounts cannot be deleted through this page.",
            "error"
        )

        return redirect(url_for("admin_dashboard"))

    has_donations = FoodDonation.query.filter_by(
        donor_id=user.id
    ).first() is not None

    has_claims = DonationClaim.query.filter_by(
        ngo_id=user.id
    ).first() is not None

    has_partner_deliveries = Delivery.query.filter_by(
        delivery_partner_id=user.id
    ).first() is not None

    has_received_deliveries = Delivery.query.filter_by(
        receiver_id=user.id
    ).first() is not None

    if (
        has_donations
        or has_claims
        or has_partner_deliveries
        or has_received_deliveries
    ):

        flash(
            "This user has associated donation, claim, or delivery "
            "records. Deactivate the account instead to preserve "
            "the platform's history.",
            "error"
        )

        return redirect(url_for("admin_dashboard"))

    try:

        user_name = user.name

        db.session.delete(user)
        db.session.commit()

        flash(
            f"User {user_name} was deleted successfully.",
            "success"
        )

    except Exception as error:

        db.session.rollback()

        print("USER DELETE ERROR:", error)

        flash(
            "Unable to delete this user.",
            "error"
        )

    return redirect(url_for("admin_dashboard"))


# ==================================================
# ADMIN: ASSIGN DELIVERY PARTNER
# ==================================================

@app.route(
    "/admin/assign-delivery/<int:delivery_id>",
    methods=["POST"]
)
@login_required
def admin_assign_delivery(delivery_id):

    if not admin_required():
        return redirect(url_for("dashboard"))

    delivery = db.session.get(
        Delivery,
        delivery_id
    )

    if not delivery:

        flash(
            "Delivery request not found.",
            "error"
        )

        return redirect(url_for("admin_dashboard"))

    if delivery.status != "Requested":

        flash(
            "Only unassigned delivery requests can be assigned.",
            "error"
        )

        return redirect(url_for("admin_dashboard"))

    if delivery.delivery_partner_id is not None:

        flash(
            "This delivery already has a delivery partner.",
            "error"
        )

        return redirect(url_for("admin_dashboard"))

    partner_id = request.form.get(
        "partner_id",
        ""
    ).strip()

    try:
        partner_id = int(partner_id)

    except (ValueError, TypeError):

        flash(
            "Please select a valid delivery partner.",
            "error"
        )

        return redirect(url_for("admin_dashboard"))

    partner = User.query.filter_by(
        id=partner_id,
        role="Delivery Partner",
        is_active=True
    ).first()

    if not partner:

        flash(
            "Selected delivery partner does not exist or is inactive.",
            "error"
        )

        return redirect(url_for("admin_dashboard"))

    try:

        ngo = delivery.receiver
        donation = delivery.donation

        delivery.delivery_partner_id = partner.id
        delivery.status = "Assigned"
        delivery.assigned_at = datetime.now()

        db.session.commit()

        # In-app notification for the NGO
        if ngo:

            create_notification(
                user_id=ngo.id,
                title="Delivery Partner Assigned",
                message=(
                    f"A delivery partner has been assigned "
                    f"to '{donation.food_name if donation else 'your donation'}'. "
                    f"Partner: {partner.name}."
                ),
                notification_type="Delivery",
                donation_id=donation.id if donation else None
            )

        # In-app notification for the delivery partner
        create_notification(
            user_id=partner.id,
            title="New Delivery Assigned",
            message=(
                f"You have been assigned a new delivery: "
                f"'{donation.food_name if donation else 'Food donation'}'. "
                "Please check your deliveries dashboard."
            ),
            notification_type="Delivery",
            donation_id=donation.id if donation else None
        )

        if ngo and ngo.email:

            send_notification_email(
                recipient=ngo.email,
                subject="Delivery Partner Assigned!",
                message=(
                    f"Hello {ngo.name},\n\n"
                    "A delivery partner has been assigned "
                    "to your food donation request.\n\n"
                    f"Food: {donation.food_name if donation else 'Food donation'}\n"
                    f"Delivery Partner: {partner.name}\n"
                    f"Email: {partner.email}\n"
                    f"Phone: {partner.phone or 'Not provided'}\n"
                    "Status: Assigned\n\n"
                    "Log in to FoodRescue AI to follow "
                    "the delivery progress.\n\n"
                    "FoodRescue AI Team"
                )
            )

        if partner.email:

            send_notification_email(
                recipient=partner.email,
                subject="New Food Delivery Assigned!",
                message=(
                    f"Hello {partner.name},\n\n"
                    "A new food delivery has been assigned to you.\n\n"
                    f"Food: {donation.food_name if donation else 'Food donation'}\n"
                    f"Quantity: {donation.quantity_kg if donation else 'Not available'} kg\n"
                    f"Pickup Address: {donation.address if donation else 'Not available'}\n"
                    f"Receiving NGO: {(ngo.organization or ngo.name) if ngo else 'Not available'}\n\n"
                    "Please log in to FoodRescue AI to view "
                    "your delivery assignment.\n\n"
                    "FoodRescue AI Team"
                )
            )

        flash(
            f"Delivery successfully assigned to {partner.name}.",
            "success"
        )

    except Exception as error:

        db.session.rollback()

        print("ADMIN ASSIGNMENT ERROR:", error)

        flash(
            "Unable to assign delivery. Please try again.",
            "error"
        )

    return redirect(url_for("admin_dashboard"))


# ==================================================
# FOOD DONATIONS WITH AI ANALYSIS AND LOCATION
# ==================================================

@app.route(
    "/donations",
    methods=["GET", "POST"]
)
@login_required
def donations():

    if not role_required("Donor"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        try:

            food_name = request.form.get(
                "food_name",
                ""
            ).strip()

            food_category = request.form.get(
                "food_category",
                ""
            ).strip()

            quantity = float(
                request.form.get("quantity_kg", 0)
            )

            expiry_value = request.form.get(
                "expiry_at",
                ""
            )

            address = request.form.get(
                "address",
                ""
            ).strip()

            description = request.form.get(
                "description",
                ""
            ).strip()

            latitude_value = request.form.get(
                "latitude",
                ""
            ).strip()

            longitude_value = request.form.get(
                "longitude",
                ""
            ).strip()

            if not food_name or not food_category or not address:

                raise ValueError(
                    "Please complete all required fields."
                )

            if quantity <= 0 or not math.isfinite(quantity):

                raise ValueError(
                    "Quantity must be a valid number greater than zero."
                )

            if food_category not in [
                "Cooked Meals",
                "Fruits",
                "Vegetables"
            ]:

                raise ValueError(
                    "Please select a supported food category."
                )

            if not expiry_value:

                raise ValueError(
                    "Please provide the food expiry time."
                )

            expiry_at = datetime.fromisoformat(expiry_value)

            if expiry_at.tzinfo is not None:

                raise ValueError(
                    "Please provide an expiry time without a timezone."
                )

            if expiry_at <= datetime.now():

                raise ValueError(
                    "Expiry time must be in the future."
                )

            if bool(latitude_value) != bool(longitude_value):

                raise ValueError(
                    "Please enter both pickup latitude and longitude, "
                    "or leave both fields empty."
                )

            if latitude_value and longitude_value:

                latitude = float(latitude_value)
                longitude = float(longitude_value)

                if not math.isfinite(latitude) or not math.isfinite(longitude):

                    raise ValueError(
                        "Pickup coordinates must be valid finite numbers."
                    )

                if not -90 <= latitude <= 90:

                    raise ValueError(
                        "Pickup latitude must be between -90 and 90."
                    )

                if not -180 <= longitude <= 180:

                    raise ValueError(
                        "Pickup longitude must be between -180 and 180."
                    )

            else:

                latitude = None
                longitude = None

            ai_result = analyze_food_donation(
                expiry_at=expiry_at,
                quantity_kg=quantity,
                food_category=food_category
            )

            donation = FoodDonation(
                donor_id=current_user.id,
                food_name=food_name,
                food_category=food_category,
                quantity_kg=quantity,
                expiry_at=expiry_at,
                address=address,
                latitude=latitude,
                longitude=longitude,
                description=description,
                urgency_score=ai_result["urgency_score"],
                urgency_level=ai_result["urgency_level"],
                predicted_demand_kg=ai_result["predicted_demand_kg"],
                surplus_kg=ai_result["surplus_kg"],
                surplus_percentage=ai_result["surplus_percentage"],
                status="Available"
            )

            db.session.add(donation)
            db.session.commit()

            flash(
                "Food donation submitted successfully! "
                f"Predicted demand: {ai_result['predicted_demand_kg']} kg. "
                f"Estimated surplus: {ai_result['surplus_kg']} kg. "
                f"Urgency: {ai_result['urgency_level']} "
                f"({ai_result['urgency_score']}/100).",
                "success"
            )

            return redirect(url_for("donations"))

        except ValueError as error:

            db.session.rollback()
            flash(str(error), "error")

        except FileNotFoundError as error:

            db.session.rollback()
            print("AI MODEL ERROR:", error)

            flash(
                "AI model is unavailable. Please contact the administrator.",
                "error"
            )

        except Exception as error:

            db.session.rollback()
            print("DONATION ERROR:", error)

            flash(
                "Something went wrong. Please try again.",
                "error"
            )

    user_donations = FoodDonation.query.filter_by(
        donor_id=current_user.id
    ).order_by(
        FoodDonation.created_at.desc()
    ).all()

    total_donations = len(user_donations)

    available_kg = sum(
        donation.quantity_kg or 0
        for donation in user_donations
        if donation.status == "Available"
    )

    completed_donations = sum(
        1 for donation in user_donations
        if donation.status == "Completed"
    )

    return render_template(
        "donations.html",
        donations=user_donations,
        total_donations=total_donations,
        available_kg=round(available_kg, 2),
        completed_donations=completed_donations
    )


# ==================================================
# NGO PROFILE
# ==================================================

@app.route(
    "/ngo-profile",
    methods=["GET", "POST"]
)
@login_required
def ngo_profile():

    if not role_required("NGO"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        try:

            service_area = request.form.get(
                "service_area",
                ""
            ).strip()

            preferred_categories = request.form.get(
                "preferred_categories",
                ""
            ).strip()

            capacity_value = request.form.get(
                "capacity_kg",
                ""
            ).strip()

            latitude_value = request.form.get(
                "latitude",
                ""
            ).strip()

            longitude_value = request.form.get(
                "longitude",
                ""
            ).strip()

            if not service_area:

                raise ValueError(
                    "Please enter your service area."
                )

            if len(service_area) > 150:

                raise ValueError(
                    "Service area cannot exceed 150 characters."
                )

            allowed_categories = {
                "cooked meals",
                "fruits",
                "vegetables"
            }

            categories = list(dict.fromkeys(
                category.strip().title()
                for category in preferred_categories.split(",")
                if category.strip()
            ))

            if not categories:

                raise ValueError(
                    "Please enter at least one preferred food category."
                )

            invalid_categories = [
                category
                for category in categories
                if category.lower() not in allowed_categories
            ]

            if invalid_categories:

                raise ValueError(
                    "Unsupported food categories: "
                    + ", ".join(invalid_categories)
                    + ". Use Cooked Meals, Fruits, or Vegetables."
                )

            preferred_categories = ", ".join(categories)

            if len(preferred_categories) > 300:

                raise ValueError(
                    "Preferred food categories are too long."
                )

            if not capacity_value:

                raise ValueError(
                    "Please enter your food handling capacity."
                )

            capacity = float(capacity_value)

            if not math.isfinite(capacity) or capacity <= 0:

                raise ValueError(
                    "Capacity must be a valid number greater than zero."
                )

            if bool(latitude_value) != bool(longitude_value):

                raise ValueError(
                    "Please enter both latitude and longitude, "
                    "or leave both fields empty."
                )

            if latitude_value and longitude_value:

                latitude = float(latitude_value)
                longitude = float(longitude_value)

                if not math.isfinite(latitude) or not math.isfinite(longitude):

                    raise ValueError(
                        "Latitude and longitude must be valid numbers."
                    )

                if not -90 <= latitude <= 90:

                    raise ValueError(
                        "Latitude must be between -90 and 90."
                    )

                if not -180 <= longitude <= 180:

                    raise ValueError(
                        "Longitude must be between -180 and 180."
                    )

            else:

                latitude = None
                longitude = None

            current_user.service_area = service_area
            current_user.preferred_categories = preferred_categories
            current_user.capacity_kg = capacity
            current_user.latitude = latitude
            current_user.longitude = longitude

            db.session.commit()

            flash(
                "NGO profile updated successfully!",
                "success"
            )

            return redirect(url_for("ngo_profile"))

        except ValueError as error:

            db.session.rollback()
            flash(str(error), "error")

        except Exception as error:

            db.session.rollback()

            print("NGO PROFILE ERROR:", error)

            flash(
                "Unable to update your profile. Please try again.",
                "error"
            )

    return render_template("ngo_profile.html")


# ==================================================
# FIND NGOs / AVAILABLE FOOD / AI NGO MATCHING
# ==================================================

@app.route("/find-ngos")
@login_required
def find_ngos():

    if current_user.role == "NGO":

        available_donations = FoodDonation.query.filter(
            FoodDonation.status == "Available",
            FoodDonation.donor_id != current_user.id,
            FoodDonation.expiry_at > datetime.now()
        ).order_by(
            FoodDonation.created_at.desc()
        ).all()

        recommended_donations = []

        for donation in available_donations:

            matches = match_ngos(
                donation,
                [current_user]
            )

            if matches:

                recommended_donations.append({
                    "donation": donation,
                    "match": matches[0]
                })

        return render_template(
            "find_ngos.html",
            donations=available_donations,
            ngos=[],
            recommended_donations=recommended_donations
        )

    elif current_user.role == "Donor":

        registered_ngos = User.query.filter_by(
            role="NGO",
            is_active=True
        ).order_by(
            User.created_at.desc()
        ).all()

        return render_template(
            "find_ngos.html",
            donations=[],
            ngos=registered_ngos,
            recommended_donations=[]
        )

    flash(
        "You do not have permission to access this page.",
        "error"
    )

    return redirect(url_for("dashboard"))


# ==================================================
# NGO CLAIMS A FOOD DONATION
# ==================================================

@app.route(
    "/claim-donation/<int:donation_id>",
    methods=["POST"]
)
@login_required
def claim_donation(donation_id):

    if not role_required("NGO"):
        return redirect(url_for("dashboard"))

    try:

        donation_record = db.session.get(
            FoodDonation,
            donation_id
        )

        if not donation_record:

            flash("Donation not found.", "error")
            return redirect(url_for("find_ngos"))

        donor = donation_record.donor

        result = db.session.query(FoodDonation).filter(
            FoodDonation.id == donation_id,
            FoodDonation.status == "Available",
            FoodDonation.expiry_at > datetime.now(),
            FoodDonation.donor_id != current_user.id
        ).update(
            {FoodDonation.status: "Claimed"},
            synchronize_session=False
        )

        if result == 0:

            db.session.rollback()

            flash(
                "This donation is no longer available or has expired.",
                "error"
            )

            return redirect(url_for("find_ngos"))

        claim = DonationClaim(
            donation_id=donation_id,
            ngo_id=current_user.id
        )

        db.session.add(claim)
        db.session.commit()

        # In-app notification for donor
        if donor:

            create_notification(
                user_id=donor.id,
                title="Food Donation Claimed!",
                message=(
                    f"Your donation '{donation_record.food_name}' "
                    f"has been claimed by "
                    f"{current_user.organization or current_user.name}."
                ),
                notification_type="Donation",
                donation_id=donation_record.id
            )

        # In-app notification for NGO
        create_notification(
            user_id=current_user.id,
            title="Donation Claim Successful!",
            message=(
                f"You successfully claimed "
                f"'{donation_record.food_name}'. "
                "You can now request delivery."
            ),
            notification_type="Donation",
            donation_id=donation_record.id
        )

        if donor and donor.email:

            send_notification_email(
                recipient=donor.email,
                subject="Your Food Donation Has Been Claimed!",
                message=(
                    f"Hello {donor.name},\n\n"
                    f"Your food donation '{donation_record.food_name}' "
                    "has been successfully claimed by an NGO.\n\n"
                    f"NGO: {current_user.organization or current_user.name}\n"
                    f"Contact: {current_user.name}\n"
                    f"Email: {current_user.email}\n"
                    f"Phone: {current_user.phone or 'Not provided'}\n\n"
                    "You can log in to FoodRescue AI to follow "
                    "the donation and delivery progress.\n\n"
                    "Thank you for helping reduce food waste!\n"
                    "FoodRescue AI Team"
                )
            )

        flash(
            "Food donation successfully claimed! "
            "You can now coordinate with the donor.",
            "success"
        )

    except Exception as error:

        db.session.rollback()
        print("CLAIM ERROR:", error)

        flash(
            "Unable to claim this donation. Please try again.",
            "error"
        )

    return redirect(url_for("find_ngos"))


# ==================================================
# NGO MY CLAIMS
# ==================================================

@app.route("/my-claims")
@login_required
def my_claims():

    if not role_required("NGO"):
        return redirect(url_for("dashboard"))

    claims = DonationClaim.query.filter_by(
        ngo_id=current_user.id
    ).order_by(
        DonationClaim.claimed_at.desc()
    ).all()

    total_claims = len(claims)

    total_quantity = sum(
        claim.donation.quantity_kg
        for claim in claims
        if claim.donation
    )

    active_claims = sum(
        1 for claim in claims
        if claim.donation
        and claim.donation.status == "Claimed"
    )

    completed_claims = sum(
        1 for claim in claims
        if claim.donation
        and claim.donation.status == "Completed"
    )

    return render_template(
        "my_claims.html",
        claims=claims,
        total_claims=total_claims,
        total_quantity=round(total_quantity, 2),
        active_claims=active_claims,
        completed_claims=completed_claims
    )


# ==================================================
# NGO REQUESTS DELIVERY + NOTIFICATIONS
# ==================================================

@app.route(
    "/request-delivery/<int:donation_id>",
    methods=["POST"]
)
@login_required
def request_delivery(donation_id):

    if not role_required("NGO"):
        return redirect(url_for("dashboard"))

    try:

        claim = DonationClaim.query.filter_by(
            donation_id=donation_id,
            ngo_id=current_user.id
        ).first()

        if not claim:

            flash(
                "You can only request delivery for food claimed by your NGO.",
                "error"
            )

            return redirect(url_for("my_claims"))

        donation = db.session.get(
            FoodDonation,
            donation_id
        )

        if not donation:

            flash("Donation not found.", "error")
            return redirect(url_for("my_claims"))

        if donation.status != "Claimed":

            flash(
                "Delivery can only be requested for an active claimed donation.",
                "error"
            )

            return redirect(url_for("my_claims"))

        if donation.expiry_at and donation.expiry_at <= datetime.now():

            flash(
                "This food donation has expired. Delivery cannot be requested.",
                "error"
            )

            return redirect(url_for("my_claims"))

        existing_delivery = Delivery.query.filter_by(
            donation_id=donation_id
        ).first()

        if existing_delivery:

            flash(
                "A delivery request already exists for this donation.",
                "error"
            )

            return redirect(url_for("my_claims"))

        delivery = Delivery(
            donation_id=donation_id,
            receiver_id=current_user.id,
            status="Requested"
        )

        db.session.add(delivery)
        db.session.commit()

        # In-app notification for donor
        donor = donation.donor

        if donor:

            create_notification(
                user_id=donor.id,
                title="Delivery Requested",
                message=(
                    f"{current_user.organization or current_user.name} "
                    f"has requested delivery for '{donation.food_name}'. "
                    "An administrator will assign a delivery partner."
                ),
                notification_type="Delivery",
                donation_id=donation.id
            )

        # In-app notification for NGO
        create_notification(
            user_id=current_user.id,
            title="Delivery Request Submitted",
            message=(
                f"Your delivery request for '{donation.food_name}' "
                "has been submitted and is awaiting admin assignment."
            ),
            notification_type="Delivery",
            donation_id=donation.id
        )

        # In-app notifications for administrators
        administrators = User.query.filter_by(
            role="Admin",
            is_active=True
        ).all()

        for admin in administrators:

            create_notification(
                user_id=admin.id,
                title="New Delivery Request",
                message=(
                    f"{current_user.organization or current_user.name} "
                    f"has requested delivery for '{donation.food_name}'. "
                    "Please assign a delivery partner."
                ),
                notification_type="Admin",
                donation_id=donation.id
            )

        # Email notification for donor
        if donor and donor.email:

            send_notification_email(
                recipient=donor.email,
                subject="Delivery Requested for Your Food Donation!",
                message=(
                    f"Hello {donor.name},\n\n"
                    f"An NGO has requested delivery for your "
                    f"food donation: {donation.food_name}.\n\n"
                    f"Food Category: {donation.food_category}\n"
                    f"Quantity: {donation.quantity_kg} kg\n"
                    f"NGO: {current_user.organization or current_user.name}\n"
                    f"NGO Contact: {current_user.name}\n"
                    f"NGO Email: {current_user.email}\n"
                    f"NGO Phone: {current_user.phone or 'Not provided'}\n\n"
                    "Current Delivery Status: Requested\n\n"
                    "The administrator will assign a delivery partner.\n"
                    "You can log in to FoodRescue AI to follow the progress.\n\n"
                    "Thank you for helping reduce food waste!\n"
                    "FoodRescue AI Team"
                )
            )

        # Email notifications for active administrators
        notified_emails = set()

        if donor and donor.email:
            notified_emails.add(donor.email)

        for admin in administrators:

            if (
                admin.email
                and admin.email not in notified_emails
            ):

                notified_emails.add(admin.email)

                send_notification_email(
                    recipient=admin.email,
                    subject="New Food Delivery Request - Admin Action Required!",
                    message=(
                        f"Hello {admin.name},\n\n"
                        "A new food delivery request has been submitted.\n\n"
                        f"Food: {donation.food_name}\n"
                        f"Category: {donation.food_category}\n"
                        f"Quantity: {donation.quantity_kg} kg\n"
                        f"Donor: {donor.name if donor else 'Not available'}\n"
                        f"Donor Email: {donor.email if donor else 'Not available'}\n"
                        f"NGO: {current_user.organization or current_user.name}\n"
                        f"NGO Contact: {current_user.email}\n"
                        f"Pickup Address: {donation.address}\n\n"
                        "Current Status: Requested\n\n"
                        "Please log in to the FoodRescue AI Admin Dashboard "
                        "and assign an available delivery partner.\n\n"
                        "FoodRescue AI Team"
                    )
                )

        flash(
            "Delivery request submitted successfully! "
            "The donor and administrators have been notified. "
            "It is waiting for admin assignment.",
            "success"
        )

    except Exception as error:

        db.session.rollback()

        print("DELIVERY REQUEST ERROR:", error)

        flash(
            "Unable to submit the delivery request. Please try again.",
            "error"
        )

    return redirect(url_for("my_claims"))


# ==================================================
# DELIVERY PARTNER: VIEW ASSIGNED DELIVERIES
# ==================================================

@app.route("/my-deliveries")
@login_required
def my_deliveries():

    if not role_required("Delivery Partner"):
        return redirect(url_for("dashboard"))

    deliveries = Delivery.query.filter_by(
        delivery_partner_id=current_user.id
    ).order_by(
        Delivery.created_at.desc()
    ).all()

    total_deliveries = len(deliveries)

    pending_deliveries = sum(
        1 for delivery in deliveries
        if delivery.status in [
            "Assigned",
            "Picked Up",
            "In Transit"
        ]
    )

    completed_deliveries = sum(
        1 for delivery in deliveries
        if delivery.status == "Delivered"
    )

    return render_template(
        "my_deliveries.html",
        deliveries=deliveries,
        total_deliveries=total_deliveries,
        pending_deliveries=pending_deliveries,
        completed_deliveries=completed_deliveries
    )


# ==================================================
# DELIVERY PARTNER: UPDATE DELIVERY STATUS
# ==================================================

@app.route(
    "/update-delivery-status/<int:delivery_id>",
    methods=["POST"]
)
@login_required
def update_delivery_status(delivery_id):

    if not role_required("Delivery Partner"):
        return redirect(url_for("dashboard"))

    delivery = Delivery.query.filter_by(
        id=delivery_id,
        delivery_partner_id=current_user.id
    ).first()

    if not delivery:

        flash(
            "Delivery not found or it is not assigned to you.",
            "error"
        )

        return redirect(url_for("my_deliveries"))

    new_status = request.form.get(
        "status",
        ""
    ).strip()

    allowed_transitions = {
        "Assigned": "Picked Up",
        "Picked Up": "In Transit",
        "In Transit": "Delivered"
    }

    expected_status = allowed_transitions.get(
        delivery.status
    )

    if not expected_status or new_status != expected_status:

        flash(
            "Invalid status update. Please follow the delivery steps in order.",
            "error"
        )

        return redirect(url_for("my_deliveries"))

    try:

        donation = delivery.donation
        ngo = delivery.receiver
        donor = donation.donor if donation else None

        delivery.status = new_status

        if new_status == "Delivered":

            delivery.completed_at = datetime.now()

            if donation:
                donation.status = "Completed"

        db.session.commit()

        # In-app notifications for donor and NGO
        if donation:

            notification_title = (
                "Food Successfully Delivered!"
                if new_status == "Delivered"
                else f"Delivery Update: {new_status}"
            )

            notification_message = (
                f"The delivery for '{donation.food_name}' "
                f"has been updated to: {new_status}."
            )

            notified_users = set()

            for recipient in [donor, ngo]:

                if (
                    recipient
                    and recipient.id not in notified_users
                ):

                    notified_users.add(recipient.id)

                    create_notification(
                        user_id=recipient.id,
                        title=notification_title,
                        message=notification_message,
                        notification_type="Delivery",
                        donation_id=donation.id
                    )

        # Existing email notifications
        if donation:

            if new_status == "Delivered":

                subject = "Food Donation Successfully Delivered!"

                message = (
                    "Hello,\n\n"
                    f"Good news! The food donation "
                    f"'{donation.food_name}' has been successfully delivered.\n\n"
                    f"Quantity: {donation.quantity_kg} kg\n"
                    f"Delivery Partner: {current_user.name}\n"
                    "Final Status: Delivered\n\n"
                    "Thank you for helping rescue surplus food "
                    "and reduce food waste!\n\n"
                    "FoodRescue AI Team"
                )

            else:

                subject = f"Delivery Update: {new_status}"

                message = (
                    "Hello,\n\n"
                    f"The delivery status for "
                    f"'{donation.food_name}' has been updated.\n\n"
                    f"Current Status: {new_status}\n"
                    f"Delivery Partner: {current_user.name}\n\n"
                    "Log in to FoodRescue AI to view the latest progress.\n\n"
                    "FoodRescue AI Team"
                )

            notified_emails = set()

            for recipient in [donor, ngo]:

                if (
                    recipient
                    and recipient.email
                    and recipient.email not in notified_emails
                ):

                    notified_emails.add(recipient.email)

                    send_notification_email(
                        recipient=recipient.email,
                        subject=subject,
                        message=message
                    )

        flash(
            f"Delivery status updated to {new_status} successfully!",
            "success"
        )

    except Exception as error:

        db.session.rollback()

        print("DELIVERY STATUS ERROR:", error)

        flash(
            "Unable to update delivery status. Please try again.",
            "error"
        )

    return redirect(url_for("my_deliveries"))


# ==================================================
# IN-APP NOTIFICATIONS PAGE
# ==================================================

@app.route("/notifications")
@login_required
def notifications():

    user_notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Notification.created_at.desc()
    ).all()

    unread_count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()

    return render_template(
        "notifications.html",
        notifications=user_notifications,
        unread_count=unread_count
    )


# ==================================================
# MARK SINGLE NOTIFICATION AS READ
# ==================================================

@app.route(
    "/notifications/<int:notification_id>/read",
    methods=["POST"]
)
@login_required
def mark_notification_read(notification_id):

    notification = Notification.query.filter_by(
        id=notification_id,
        user_id=current_user.id
    ).first()

    if not notification:

        flash(
            "Notification not found.",
            "error"
        )

        return redirect(url_for("notifications"))

    try:

        notification.is_read = True

        db.session.commit()

        flash(
            "Notification marked as read.",
            "success"
        )

    except Exception as error:

        db.session.rollback()

        print("MARK NOTIFICATION READ ERROR:", error)

        flash(
            "Unable to update notification.",
            "error"
        )

    return redirect(url_for("notifications"))


# ==================================================
# MARK ALL NOTIFICATIONS AS READ
# ==================================================

@app.route(
    "/notifications/mark-all-read",
    methods=["POST"]
)
@login_required
def mark_all_notifications_read():

    try:

        Notification.query.filter_by(
            user_id=current_user.id,
            is_read=False
        ).update(
            {Notification.is_read: True},
            synchronize_session=False
        )

        db.session.commit()

        flash(
            "All notifications marked as read.",
            "success"
        )

    except Exception as error:

        db.session.rollback()

        print("MARK ALL NOTIFICATIONS ERROR:", error)

        flash(
            "Unable to update notifications.",
            "error"
        )

    return redirect(url_for("notifications"))


# ==================================================
# AI INSIGHTS DASHBOARD
# ==================================================

@app.route("/ai-insights")
@login_required
def ai_insights():

    if current_user.role == "Donor":

        insights_donations = FoodDonation.query.filter_by(
            donor_id=current_user.id
        ).all()

    elif current_user.role == "NGO":

        insights_donations = FoodDonation.query.join(
            DonationClaim,
            FoodDonation.id == DonationClaim.donation_id
        ).filter(
            DonationClaim.ngo_id == current_user.id
        ).all()

    elif current_user.role == "Delivery Partner":

        partner_deliveries = Delivery.query.filter_by(
            delivery_partner_id=current_user.id
        ).all()

        insights_donations = [
            delivery.donation
            for delivery in partner_deliveries
            if delivery.donation
        ]

    elif current_user.role == "Admin":

        insights_donations = FoodDonation.query.all()

    else:

        insights_donations = []

    insights_donations = list({
        donation.id: donation
        for donation in insights_donations
    }.values())

    total_donations = len(insights_donations)

    total_quantity = sum(
        donation.quantity_kg or 0
        for donation in insights_donations
    )

    analyzed_donations = [
        donation
        for donation in insights_donations
        if donation.predicted_demand_kg is not None
    ]

    predicted_demand = sum(
        donation.predicted_demand_kg or 0
        for donation in analyzed_donations
    )

    estimated_surplus = sum(
        donation.surplus_kg or 0
        for donation in analyzed_donations
    )

    urgency_donations = [
        donation
        for donation in insights_donations
        if donation.urgency_score is not None
    ]

    average_urgency = (
        sum(
            donation.urgency_score
            for donation in urgency_donations
        ) / len(urgency_donations)
        if urgency_donations else 0
    )

    urgency_counts = {
        "Critical": 0,
        "High": 0,
        "Medium": 0,
        "Low": 0
    }

    for donation in insights_donations:

        level = (
            donation.urgency_level or ""
        ).capitalize()

        if level in urgency_counts:
            urgency_counts[level] += 1

    category_counts = {}

    for donation in insights_donations:

        category = donation.food_category or "Other"

        category_counts[category] = (
            category_counts.get(category, 0) + 1
        )

    urgent_donations = sorted(
        urgency_donations,
        key=lambda donation: donation.urgency_score or 0,
        reverse=True
    )[:5]

    return render_template(
        "ai_insights.html",
        total_donations=total_donations,
        total_quantity=round(total_quantity, 2),
        analyzed_count=len(analyzed_donations),
        predicted_demand=round(predicted_demand, 2),
        estimated_surplus=round(estimated_surplus, 2),
        average_urgency=round(average_urgency, 1),
        urgency_counts=urgency_counts,
        category_counts=category_counts,
        urgent_donations=urgent_donations
    )


# ==================================================
# HEALTH CHECK
# ==================================================

@app.route("/health")
def health():

    return {
        "status": "online",
        "application": "FoodRescue AI"
    }


# ==================================================
# DATABASE MIGRATION: USERS TABLE
# ==================================================

def migrate_user_table():

    inspector = inspect(db.engine)

    if "users" not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"]
        for column in inspector.get_columns("users")
    }

    new_columns = {
        "service_area": "VARCHAR(150)",
        "latitude": "FLOAT",
        "longitude": "FLOAT",
        "preferred_categories": "VARCHAR(300)",
        "capacity_kg": "FLOAT",
        "is_active": "BOOLEAN NOT NULL DEFAULT 1"
    }

    with db.engine.begin() as connection:

        for column_name, column_type in new_columns.items():

            if column_name not in existing_columns:

                connection.execute(
                    text(
                        f"ALTER TABLE users ADD COLUMN "
                        f"{column_name} {column_type}"
                    )
                )

                print(
                    f"Database update: users.{column_name} added."
                )


# ==================================================
# DATABASE MIGRATION: DELIVERIES TABLE
# ==================================================

def migrate_delivery_table():

    inspector = inspect(db.engine)

    if "deliveries" not in inspector.get_table_names():
        return

    columns = {
        column["name"]
        for column in inspector.get_columns("deliveries")
    }

    if "created_at" not in columns:

        with db.engine.begin() as connection:

            connection.execute(
                text(
                    "ALTER TABLE deliveries "
                    "ADD COLUMN created_at DATETIME"
                )
            )

            connection.execute(
                text(
                    "UPDATE deliveries "
                    "SET created_at = CURRENT_TIMESTAMP "
                    "WHERE created_at IS NULL"
                )
            )

        print(
            "Database update: deliveries.created_at added."
        )


# ==================================================
# DATABASE MIGRATION: FOOD DONATIONS TABLE
# ==================================================

def migrate_food_donations_table():

    inspector = inspect(db.engine)

    if "food_donations" not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"]
        for column in inspector.get_columns("food_donations")
    }

    new_columns = {
        "urgency_level": "VARCHAR(30)",
        "predicted_demand_kg": "FLOAT",
        "surplus_kg": "FLOAT",
        "surplus_percentage": "FLOAT",
        "latitude": "FLOAT",
        "longitude": "FLOAT"
    }

    with db.engine.begin() as connection:

        for column_name, column_type in new_columns.items():

            if column_name not in existing_columns:

                connection.execute(
                    text(
                        f"ALTER TABLE food_donations "
                        f"ADD COLUMN {column_name} {column_type}"
                    )
                )

                print(
                    f"Database update: "
                    f"food_donations.{column_name} added."
                )


# ==================================================
# APPLICATION START
# ==================================================

if __name__ == "__main__":

    with app.app_context():

        db.create_all()

        migrate_user_table()
        migrate_delivery_table()
        migrate_food_donations_table()

    app.run(debug=True)
