from app import app, db, Admin
from werkzeug.security import generate_password_hash
from datetime import datetime

# This script helps set up an admin account or fix admin account issues

with app.app_context():
    # Check if admin table exists
    try:
        admin_count = Admin.query.count()
        print(f"Found {admin_count} admin accounts in the database.")
        
        # Option to create a new admin
        create_new = input("Would you like to create a new admin account? (y/n): ")
        if create_new.lower() == 'y':
            username = input("Enter admin username: ")
            email = input("Enter admin email: ")
            password = input("Enter admin password: ")
            
            new_admin = Admin(
                username=username,
                email=email,
                password=generate_password_hash(password),
                is_super_admin=True,
                created_at=datetime.utcnow()
            )
            
            db.session.add(new_admin)
            db.session.commit()
            print(f"Created new admin account with ID: {new_admin.admin_id}")
        
        # Option to list all admins
        list_admins = input("Would you like to list all admin accounts? (y/n): ")
        if list_admins.lower() == 'y':
            admins = Admin.query.all()
            print("\nAll admin accounts:")
            for admin in admins:
                print(f"ID: {admin.admin_id}, Username: {admin.username}, Email: {admin.email}, Super Admin: {admin.is_super_admin}")
        
        # Option to reset an admin password
        reset_pw = input("Would you like to reset an admin password? (y/n): ")
        if reset_pw.lower() == 'y':
            admin_id = input("Enter admin ID: ")
            new_password = input("Enter new password: ")
            
            admin = Admin.query.get(int(admin_id))
            if admin:
                admin.password = generate_password_hash(new_password)
                db.session.commit()
                print(f"Password reset for admin {admin.username}")
            else:
                print("Admin not found with that ID")
                
    except Exception as e:
        print(f"Error accessing admin table: {str(e)}")
        create_table = input("Would you like to create the admin table? (y/n): ")
        
        if create_table.lower() == 'y':
            db.create_all()
            print("Tables created successfully!")
            
            # Create first admin
            username = input("Enter admin username for the first admin: ")
            email = input("Enter admin email: ")
            password = input("Enter admin password: ")
            
            first_admin = Admin(
                username=username,
                email=email,
                password=generate_password_hash(password),
                is_super_admin=True,
                created_at=datetime.utcnow()
            )
            
            db.session.add(first_admin)
            db.session.commit()
            print(f"Created first admin account with ID: {first_admin.admin_id}")

#Name:Ethan Williams
#Student Number: 24026055