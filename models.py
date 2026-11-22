
from datetime import datetime
from flask_login import UserMixin
from extensions import db


# ==================================================
# USER MODEL
# ==================================================

class User(UserMixin, db.Model):

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    role = db.Column(db.String(30), nullable=False)
    organization = db.Column(db.String(150))
    phone = db.Column(db.String(20))

    is_active = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    # NGO matching information
    service_area = db.Column(db.String(150))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    preferred_categories = db.Column(db.String(300))
    capacity_kg = db.Column(db.Float)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    # Donations created by donor
    donations = db.relationship(
        "FoodDonation",
        back_populates="donor",
        lazy=True,
        foreign_keys="FoodDonation.donor_id"
    )

    # Donations claimed by NGO
    claimed_donations = db.relationship(
        "DonationClaim",
        back_populates="ngo",
        lazy=True,
        foreign_keys="DonationClaim.ngo_id"
    )

    # Deliveries assigned to partner
    deliveries_as_partner = db.relationship(
        "Delivery",
        back_populates="delivery_partner",
        lazy=True,
        foreign_keys="Delivery.delivery_partner_id"
    )

    # Deliveries received by NGO
    received_deliveries = db.relationship(
        "Delivery",
        back_populates="receiver",
        lazy=True,
        foreign_keys="Delivery.receiver_id"
    )

    # In-app notifications
    notifications = db.relationship(
        "Notification",
        back_populates="user",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="Notification.created_at.desc()"
    )


# ==================================================
# PENDING REGISTRATION MODEL
# ==================================================

class PendingRegistration(db.Model):

    __tablename__ = "pending_registrations"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    role = db.Column(db.String(30), nullable=False)
    organization = db.Column(db.String(150))
    phone = db.Column(db.String(20))

    otp_hash = db.Column(db.String(255), nullable=False)
    otp_expiry = db.Column(db.DateTime, nullable=False)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# ==================================================
# FOOD DONATION MODEL
# ==================================================

class FoodDonation(db.Model):

    __tablename__ = "food_donations"

    id = db.Column(db.Integer, primary_key=True)

    donor_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    food_name = db.Column(db.String(120), nullable=False)
    food_category = db.Column(db.String(80))
    quantity_kg = db.Column(db.Float, nullable=False)

    prepared_at = db.Column(db.DateTime)
    expiry_at = db.Column(db.DateTime)

    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    address = db.Column(db.String(250))

    description = db.Column(db.Text)

    status = db.Column(
        db.String(30),
        default="Available"
    )

    # AI urgency analysis
    urgency_score = db.Column(db.Float, default=0.0)
    urgency_level = db.Column(db.String(30))

    # AI demand prediction
    predicted_demand_kg = db.Column(db.Float)
    surplus_kg = db.Column(db.Float)
    surplus_percentage = db.Column(db.Float)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    # Donor relationship
    donor = db.relationship(
        "User",
        back_populates="donations",
        foreign_keys=[donor_id]
    )

    # One claim per donation
    claim = db.relationship(
        "DonationClaim",
        back_populates="donation",
        uselist=False,
        lazy=True,
        cascade="all, delete-orphan"
    )

    # One delivery per donation
    delivery = db.relationship(
        "Delivery",
        back_populates="donation",
        uselist=False,
        lazy=True,
        cascade="all, delete-orphan"
    )


# ==================================================
# DONATION CLAIM MODEL
# ==================================================

class DonationClaim(db.Model):

    __tablename__ = "donation_claims"

    id = db.Column(db.Integer, primary_key=True)

    donation_id = db.Column(
        db.Integer,
        db.ForeignKey("food_donations.id"),
        nullable=False,
        unique=True
    )

    ngo_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    claimed_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    donation = db.relationship(
        "FoodDonation",
        back_populates="claim"
    )

    ngo = db.relationship(
        "User",
        back_populates="claimed_donations",
        foreign_keys=[ngo_id]
    )


# ==================================================
# DELIVERY MODEL
# ==================================================

class Delivery(db.Model):

    __tablename__ = "deliveries"

    id = db.Column(db.Integer, primary_key=True)

    donation_id = db.Column(
        db.Integer,
        db.ForeignKey("food_donations.id"),
        nullable=False,
        unique=True
    )

    # NGO receiving the donation
    receiver_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id")
    )

    # Assigned delivery partner
    delivery_partner_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id")
    )

    status = db.Column(
        db.String(30),
        default="Requested",
        nullable=False
    )

    assigned_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    # Related food donation
    donation = db.relationship(
        "FoodDonation",
        back_populates="delivery"
    )

    # NGO receiving food
    receiver = db.relationship(
        "User",
        back_populates="received_deliveries",
        foreign_keys=[receiver_id]
    )

    # Assigned delivery partner
    delivery_partner = db.relationship(
        "User",
        back_populates="deliveries_as_partner",
        foreign_keys=[delivery_partner_id]
    )


# ==================================================
# IN-APP NOTIFICATION MODEL
# ==================================================

class Notification(db.Model):

    __tablename__ = "notifications"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # User receiving notification
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    # Notification heading
    title = db.Column(
        db.String(150),
        nullable=False
    )

    # Notification description
    message = db.Column(
        db.Text,
        nullable=False
    )

    # Notification category
    notification_type = db.Column(
        db.String(50),
        default="General"
    )

    # Related donation, if applicable
    donation_id = db.Column(
        db.Integer,
        db.ForeignKey("food_donations.id"),
        nullable=True
    )

    # Read/unread tracking
    is_read = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # User relationship
    user = db.relationship(
        "User",
        back_populates="notifications"
    )

    # Related donation
    donation = db.relationship(
        "FoodDonation",
        foreign_keys=[donation_id]
    )
