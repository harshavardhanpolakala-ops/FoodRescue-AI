
import os
import re
import json
import secrets
import urllib.request
import urllib.error

from datetime import datetime, timedelta

from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, session, current_app
)

from flask_login import (
    login_user, logout_user, login_required, current_user
)

from werkzeug.security import (
    generate_password_hash, check_password_hash
)

from extensions import db
from models import User, PendingRegistration


auth = Blueprint("auth", __name__)


# --------------------------------------------------
# EMAIL VALIDATION
# --------------------------------------------------

def is_valid_email(email):
    pattern = r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$"
    return bool(re.fullmatch(pattern, email))


# --------------------------------------------------
# SEND OTP USING BREVO API
# --------------------------------------------------

def send_otp_email(email, otp):

    api_key = os.environ.get("BREVO_API_KEY")

    if not api_key:
        raise RuntimeError("BREVO_API_KEY is not configured.")

    sender_email = "harshavardhanpolakala@gmail.com"

    payload = {
        "sender": {
            "name": "FoodRescue AI",
            "email": sender_email
        },
        "to": [
            {
                "email": email
            }
        ],
        "subject": "FoodRescue AI - Email Verification",
        "textContent": (
            "Hello!\n\n"
            "Thank you for registering with FoodRescue AI.\n\n"
            f"Your email verification code is: {otp}\n\n"
            "This code expires in 5 minutes.\n\n"
            "If you did not request this verification, please ignore this email.\n\n"
            "Regards,\n"
            "FoodRescue AI Team"
        )
    }

    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=data,
        headers={
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            if response.status not in (200, 201):
                raise RuntimeError(
                    f"Brevo returned status {response.status}"
                )

            print("OTP email accepted by Brevo.")

    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        print("BREVO API ERROR:", error.code, details)
        raise RuntimeError("Brevo could not send the verification email.")

    except urllib.error.URLError as error:
        print("BREVO CONNECTION ERROR:", error)
        raise RuntimeError("Could not connect to Brevo.")


# --------------------------------------------------
# REGISTRATION
# --------------------------------------------------

@auth.route("/register", methods=["GET", "POST"])
def register():

    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "")
        organization = request.form.get("organization", "").strip()
        phone = request.form.get("phone", "").strip()

        allowed_roles = ["Donor", "NGO", "Delivery Partner"]

        if not name or not email or not password or not role:
            flash("Please fill in all required fields.", "error")
            return redirect(url_for("auth.register"))

        if not is_valid_email(email):
            flash("Please enter a valid email address.", "error")
            return redirect(url_for("auth.register"))

        if role not in allowed_roles:
            flash("Please select a valid account role.", "error")
            return redirect(url_for("auth.register"))

        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
            return redirect(url_for("auth.register"))

        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            flash("An account with this email already exists.", "error")
            return redirect(url_for("auth.register"))

        pending = PendingRegistration.query.filter_by(
            email=email
        ).first()

        otp = str(secrets.randbelow(900000) + 100000)

        if pending:

            pending.name = name
            pending.password_hash = generate_password_hash(password)
            pending.role = role
            pending.organization = organization
            pending.phone = phone
            pending.otp_hash = generate_password_hash(otp)
            pending.otp_expiry = datetime.utcnow() + timedelta(minutes=5)

        else:

            pending = PendingRegistration(
                name=name,
                email=email,
                password_hash=generate_password_hash(password),
                role=role,
                organization=organization,
                phone=phone,
                otp_hash=generate_password_hash(otp),
                otp_expiry=datetime.utcnow() + timedelta(minutes=5)
            )

            db.session.add(pending)

        db.session.commit()

        try:

            send_otp_email(email, otp)

            session["pending_email"] = email

            flash(
                "A 6-digit verification code has been sent to your email.",
                "success"
            )

            return redirect(url_for("auth.verify_email"))

        except Exception as error:

            print("EMAIL ERROR:", error)

            db.session.delete(pending)
            db.session.commit()

            flash(
                "Unable to send verification email. Please try again.",
                "error"
            )

            return redirect(url_for("auth.register"))

    return render_template("register.html")


# --------------------------------------------------
# EMAIL VERIFICATION
# --------------------------------------------------

@auth.route("/verify-email", methods=["GET", "POST"])
def verify_email():

    email = session.get("pending_email")

    if not email:
        flash("Please register before verifying your email.", "error")
        return redirect(url_for("auth.register"))

    pending = PendingRegistration.query.filter_by(
        email=email
    ).first()

    if not pending:

        session.pop("pending_email", None)

        flash(
            "Registration details were not found. Please register again.",
            "error"
        )

        return redirect(url_for("auth.register"))

    if request.method == "POST":

        otp = request.form.get("otp", "").strip()

        if not otp.isdigit() or len(otp) != 6:
            flash("Please enter a valid 6-digit verification code.", "error")
            return redirect(url_for("auth.verify_email"))

        if datetime.utcnow() > pending.otp_expiry:

            db.session.delete(pending)
            db.session.commit()

            session.pop("pending_email", None)

            flash(
                "Your verification code has expired. Please register again.",
                "error"
            )

            return redirect(url_for("auth.register"))

        if not check_password_hash(pending.otp_hash, otp):

            flash(
                "Incorrect verification code. Please try again.",
                "error"
            )

            return redirect(url_for("auth.verify_email"))

        user = User(
            name=pending.name,
            email=pending.email,
            password_hash=pending.password_hash,
            role=pending.role,
            organization=pending.organization,
            phone=pending.phone
        )

        db.session.add(user)
        db.session.delete(pending)
        db.session.commit()

        session.pop("pending_email", None)

        login_user(user)

        flash(
            "Your email has been verified and your account is ready!",
            "success"
        )

        return redirect(url_for("dashboard"))

    return render_template("verify_email.html", email=email)


# --------------------------------------------------
# RESEND OTP
# --------------------------------------------------

@auth.route("/resend-otp", methods=["POST"])
def resend_otp():

    email = session.get("pending_email")

    if not email:

        flash(
            "Please register again to request a verification code.",
            "error"
        )

        return redirect(url_for("auth.register"))

    pending = PendingRegistration.query.filter_by(
        email=email
    ).first()

    if not pending:

        session.pop("pending_email", None)

        flash("Registration details were not found.", "error")

        return redirect(url_for("auth.register"))

    otp = str(secrets.randbelow(900000) + 100000)

    pending.otp_hash = generate_password_hash(otp)
    pending.otp_expiry = datetime.utcnow() + timedelta(minutes=5)

    db.session.commit()

    try:

        send_otp_email(email, otp)

        flash(
            "A new verification code has been sent.",
            "success"
        )

    except Exception as error:

        print("EMAIL ERROR:", error)

        flash(
            "Unable to resend the verification code. Please try again.",
            "error"
        )

    return redirect(url_for("auth.verify_email"))


# --------------------------------------------------
# LOGIN
# --------------------------------------------------

@auth.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):

            if not user.is_active:

                flash(
                    "Your account has been deactivated. Please contact the administrator.",
                    "error"
                )

                return redirect(url_for("auth.login"))

            login_user(user)

            flash("Welcome back!", "success")

            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


# --------------------------------------------------
# LOGOUT
# --------------------------------------------------

@auth.route("/logout")
@login_required
def logout():

    logout_user()

    flash("You have been logged out.", "success")

    return redirect(url_for("auth.login"))
