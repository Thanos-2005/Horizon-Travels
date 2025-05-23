from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import logging

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://admin:Rose2015@127.0.0.1:3307/horizontravelsdbv2'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'

db = SQLAlchemy(app)

logging.basicConfig(level=logging.DEBUG)

with app.app_context():
    try:
        print("Testing database connection...")
        with db.engine.connect() as connection:
            print("Database connection successful!")
    except Exception as e:
        print(f"Error connecting to database: {e}")

@app.route('/')
def index():
    return redirect(url_for('home'))

@app.before_request
def clear_session_on_restart():
    if not session.get('initialized'):
        session.clear()  # Clear the session
        session['initialized'] = True  # Mark the session as initialized

# WebsiteUser table
class WebsiteUser(db.Model):
    __tablename__ = 'websiteusers'
    UserID = db.Column(db.Integer, primary_key=True)
    FirstName = db.Column(db.String(45), nullable=False)
    LastName = db.Column(db.String(45), nullable=False)
    PhoneNumber = db.Column(db.String(45), nullable=False)
    AddressLine = db.Column(db.String(45), nullable=False)
    UserCity = db.Column(db.String(45), nullable=False)
    PostCode = db.Column(db.String(45), nullable=False)
    BirthDate = db.Column(db.Date, nullable=False)
    EmailAddress = db.Column(db.String(45), unique=True, nullable=False)
    UserPassword = db.Column(db.String(150), nullable=False)

# SiteAdmin table
class SiteAdmin(db.Model):
    __tablename__ = 'siteadmin'
    AdminID = db.Column(db.Integer, primary_key=True)
    AdminName = db.Column(db.String(45), nullable=False)
    AdminEmail = db.Column(db.String(45), unique=True, nullable=False)
    AdminPassword = db.Column(db.String(150), nullable=False)

# JourneyDetails table
class JourneyDetails(db.Model):
    __tablename__ = 'journeydetails'
    JourneyID = db.Column(db.Integer, primary_key=True)
    DepartLocation = db.Column(db.String(100), nullable=False)
    ArriveLocation = db.Column(db.String(100), nullable=False)
    DepartTime = db.Column(db.Time, nullable=False)  # Ensure this is db.Time
    ArriveTime = db.Column(db.Time, nullable=False)  # Ensure this is db.Time

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form['first-name']
        last_name = request.form['last-name']
        phone_number = request.form['phone-number']
        address = request.form['address']
        user_city = request.form['user-city']
        post_code = request.form['post-code']
        birth_date = request.form['birth-date']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm-password']

        logging.debug(f"Received data: {first_name}, {last_name}, {phone_number}, {address}, {user_city}, {post_code}, {birth_date}, {email}")

        # Check if passwords match
        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return redirect(url_for('register'))

        # Hash the password
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)

        # Create a new user object
        new_user = WebsiteUser(
            FirstName=first_name,
            LastName=last_name,
            PhoneNumber=phone_number,
            AddressLine=address,
            UserCity=user_city,
            PostCode=post_code,
            BirthDate=birth_date,
            EmailAddress=email,
            UserPassword=hashed_password
        )

        try:
            # Add the new user to the database session
            db.session.add(new_user)
            db.session.commit()  # Commit the transaction to save the data
            logging.info(f"User {email} successfully registered.")
            flash('Registration successful!', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            # Rollback the transaction in case of an error
            db.session.rollback()
            logging.error(f"Error inserting user {email} into the database: {str(e)}")
            flash(f'Error: {str(e)}', 'danger')
            return redirect(url_for('register'))

    # Render the registration page for GET requests
    return render_template('RegisterPage.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        logging.debug(f"Login attempt with email: {email}")

        # Check if the user is an admin
        admin = SiteAdmin.query.filter_by(AdminEmail=email).first()
        if admin:
            logging.debug(f"Admin found: {admin.AdminName}")
        if admin and admin.AdminPassword == password:  # Compare plain text password for admin
            session['admin_id'] = admin.AdminID
            session['admin_name'] = admin.AdminName
            flash(f'Admin {admin.AdminName} logged in successfully!', 'success')
            return redirect(url_for('home'))

        # Check if the user is a normal user
        user = WebsiteUser.query.filter_by(EmailAddress=email).first()
        if user:
            logging.debug(f"User found: {user.FirstName}")
        if user and check_password_hash(user.UserPassword, password):  # Verify hashed password for user
            session['user_id'] = user.UserID
            session['user_name'] = user.FirstName
            flash(f'User {user.FirstName} logged in successfully!', 'success')
            return redirect(url_for('home'))

        # Login failed
        logging.debug("Login failed: Invalid email or password")
        flash('Invalid email or password!', 'danger')
        return redirect(url_for('login'))

    return render_template('LoginPage.html')

@app.route('/home')
def home():
    admin_logged_in = 'admin_name' in session
    user_logged_in = 'user_name' in session
    return render_template('HomePage.html', admin_logged_in=admin_logged_in, user_logged_in=user_logged_in, session=session)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/booking', methods=['GET', 'POST'])
def booking():
    if request.method == 'POST':
        depart_location = request.form['depart-location']
        arrive_location = request.form['arrive-location']

        # Query the database for the selected journey details
        journey = JourneyDetails.query.filter_by(DepartLocation=depart_location, ArriveLocation=arrive_location).first()

        if journey:
            # Store the journey details in the session for later use
            session['journey_id'] = journey.JourneyID
            session['depart_time'] = journey.DepartTime
            session['arrive_time'] = journey.ArriveTime
            flash('Journey details selected successfully!', 'success')
            return redirect(url_for('booking_date'))

        flash('Invalid journey selection!', 'danger')
        return redirect(url_for('booking'))

    # Query the database for all unique departure locations
    depart_locations = db.session.query(JourneyDetails.DepartLocation).distinct().all()
    return render_template('BookingDestination.html', depart_locations=depart_locations)


@app.route('/booking-date', methods=['GET', 'POST'])
def booking_date():
    if request.method == 'POST':
        booking_date = request.form['booking-date']

        # Ensure the booking date is valid
        if booking_date:
            session['booking_date'] = booking_date
            flash('Booking date selected successfully!', 'success')
            return redirect(url_for('payment'))

        flash('Invalid booking date!', 'danger')
        return redirect(url_for('booking_date'))

    return render_template('BookingDate.html')


@app.route('/payment', methods=['GET'])
def payment():
    # Placeholder for payment details
    return "Payment details page (to be implemented)."

@app.route('/get-arrival-locations', methods=['GET'])
def get_arrival_locations():
    depart_location = request.args.get('depart_location')

    # Query the database for arrival locations based on the selected departure location
    arrival_locations = JourneyDetails.query.filter_by(DepartLocation=depart_location).all()

    # Use a set to ensure unique arrival locations
    unique_arrival_locations = {journey.ArriveLocation for journey in arrival_locations}

    # Prepare the data to send back as JSON
    arrival_data = [{'ArriveLocation': location} for location in unique_arrival_locations]

    return jsonify({'arrival_locations': arrival_data})

@app.route('/get-journey-details', methods=['GET'])
def get_journey_details():
    depart_location = request.args.get('depart_location')
    arrive_location = request.args.get('arrive_location')

    # Query the database for all journeys with the selected departure and arrival locations
    journeys = JourneyDetails.query.filter_by(DepartLocation=depart_location, ArriveLocation=arrive_location).all()

    if journeys:
        # Prepare the data to send back as JSON
        journey_data = [
            {
                'depart_time': journey.DepartTime.strftime('%H:%M:%S'),  # Format time as string
                'arrive_time': journey.ArriveTime.strftime('%H:%M:%S')
            }
            for journey in journeys
        ]
        return jsonify({'journey_times': journey_data})

    return jsonify({'error': 'No journeys found'}), 404

if __name__ == '__main__':
    app.run(debug=True)

    #Name:Ethan Williams
#Student Number: 24026055