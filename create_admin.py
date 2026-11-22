
from getpass import getpass

from app import app
from extensions import db
from models import User
from werkzeug.security import generate_password_hash


def create_admin():
    print("\n===== FoodRescue AI Admin Setup =====\n")

    name = input("Enter admin name: ").strip()
    email = input("Enter admin email: ").strip().lower()

    password = getpass("Enter admin password: ")
    confirm_password = getpass("Confirm admin password: ")

    if not name or not email:
        print("\nName and email are required.")
        return

    if len(password) < 8:
        print("\nPassword must contain at least 8 characters.")
        return

    if password != confirm_password:
        print("\nPasswords do not match.")
        return

    with app.app_context():
        db.create_all()

        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            print("\nAn account with this email already exists.")
            return

        admin = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
            role="Admin"
        )

        try:
            db.session.add(admin)
            db.session.commit()
            print("\nAdmin account created successfully!")

        except Exception as error:
            db.session.rollback()
            print("\nUnable to create admin account:", error)


if __name__ == "__main__":
    create_admin()
