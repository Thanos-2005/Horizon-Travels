# save as create_admin.py
from app import app, db, Admin
from werkzeug.security import generate_password_hash
from datetime import datetime

# This script helps create an admin account directly

with app.app_context():
    print("Creating new admin account...")
    
    email = "admin@horizon.com"
    password = "admin123"
    
    # Check if admin already exists
    existing = Admin.query.filter_by(email=email).first()
    if existing:
        print(f"Admin with email {email} already exists!")
        exit()
    
    # Create admin
    new_admin = Admin(
        username=email,
        email=email,
        password=generate_password_hash(password),
        is_super_admin=True,
        created_at=datetime.utcnow()
    )
    
    try:
        db.session.add(new_admin)
        db.session.commit()
        print(f"Admin created successfully! ID: {new_admin.admin_id}")
        print(f"Login details:")
        print(f"Username: {email}")
        print(f"Password: {password}")
    except Exception as e:
        print(f"Error creating admin: {str(e)}")

#Name:Ethan Williams
#Student Number: 24026055