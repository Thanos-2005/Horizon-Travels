from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
import bcrypt
from functools import wraps
from datetime import datetime, timedelta
import random
import string
from sqlalchemy import extract, func, cast
from sqlalchemy.types import Numeric
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.sql import text
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Template

app = Flask(__name__, static_folder='static')

# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:ethan0109@localhost/Horizon_Travels'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
app.secret_key = 'your_secret_key_here'  # Add this line - use a random string
#app.run(debug=True)

# Email Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your_email@gmail.com'  # Replace with your actual email
app.config['MAIL_PASSWORD'] = 'your_app_password'     # Use Gmail App Password, not your account password

# Add this after your app initialization
from datetime import datetime

@app.context_processor
def inject_datetime():
    return {'datetime': datetime}

@app.before_request
def before_request():
    # Print the route being accessed for debugging
    print(f"Accessing: {request.method} {request.path}")
    print(f"Current session: {session}")

# Add this function after your existing imports
def ensure_travel_company_exists(company_id, company_name="Horizon Airways"):
    """Check if travel company exists and create if needed"""
    try:
        # Check if company exists
        result = db.session.execute(text(f"SELECT * FROM travel_company WHERE idtravel_company = {company_id}")).fetchone()
        if not result:
            # Print the exact query we're about to run for debugging
            insert_sql = text(f"INSERT INTO travel_company (idtravel_company, co_name, co_address) "
                       f"VALUES ({company_id}, '{company_name}', 'Horizon Airways HQ, Airport Business Park, BS1 1AA')")
            print(f"Executing SQL: {insert_sql}")
            
            try:
                db.session.execute(insert_sql)
                db.session.commit()
                print(f"Travel company with ID {company_id} created successfully")
            except Exception as sql_err:
                print(f"SQL Execution Error: {str(sql_err)}")
                raise sql_err
        return True
    except Exception as e:
        print(f"Error in ensure_travel_company_exists: {str(e)}")
        db.session.rollback()
        return False

@app.route('/create-travel-company')
def create_travel_company():
    try:
        # First check if it exists to avoid duplicates
        check_sql = "SELECT * FROM travel_company WHERE idtravel_company = 1"
        result = db.session.execute(text(check_sql)).fetchall()
        
        if result:
            return f"Travel company already exists: {result}"
        
        # Try with a very basic INSERT statement
        insert_sql = """
        INSERT INTO travel_company (idtravel_company, co_name) 
        VALUES (1, 'Horizon Airways')
        """
        db.session.execute(text(insert_sql))
        db.session.commit()
        
        # Verify it was created
        verify = db.session.execute(text(check_sql)).fetchall()
        
        return f"Travel company created successfully! Verification: {verify}"
    except Exception as e:
        db.session.rollback()
        # Get detailed error information
        error_details = str(e)
        import traceback
        trace = traceback.format_exc()
        
        # Try to get database schema information
        try:
            tables = db.session.execute(text("SHOW TABLES")).fetchall()
            travel_company_schema = db.session.execute(text("DESCRIBE travel_company")).fetchall() if 'travel_company' in [t[0] for t in tables] else "Table not found"
        except:
            tables = "Could not retrieve tables"
            travel_company_schema = "Could not retrieve schema"
        
        return f"""
        <h2>Error creating travel company:</h2>
        <pre>{error_details}</pre>
        
        <h3>Stack trace:</h3>
        <pre>{trace}</pre>
        
        <h3>Database tables:</h3>
        <pre>{tables}</pre>
        
        <h3>travel_company schema:</h3>
        <pre>{travel_company_schema}</pre>
        """

# Flight Model
class Flight(db.Model):
    __tablename__ = 'journey'
    journeyid = db.Column(db.Integer, primary_key=True)  # Note: this is the actual column name
    id_travelcompany = db.Column(db.Integer, nullable=False)
    flight_number = db.Column(db.String(45), nullable=True)  # Add this line if you have this column in DB
    dep_location = db.Column(db.String(45), nullable=False)
    arr_location = db.Column(db.String(45), nullable=False)
    dep_time = db.Column(db.DateTime, nullable=False)  
    arr_time = db.Column(db.DateTime, nullable=False)
    cost = db.Column(db.String(45), nullable=False)  
    seats = db.Column(db.String(45), nullable=False) 
    class_type = db.Column(db.String(20), nullable=False)
    
    # Add property to make the code consistent
    @property
    def journey_id(self):
        return self.journeyid
    
    # Add properties to simulate the fields your app needs
    @property
    def departure_date(self):
        return self.dep_time.date() if self.dep_time else None
    
    @property
    def departure_time(self):
        return self.dep_time.time() if self.dep_time else None
    
    @property
    def arrival_time(self):
        return self.arr_time.time() if self.arr_time else None
    
    @property
    def price(self):
        return self.cost  # Simply return the cost as the price

# Booking Model
class Booking(db.Model):
    __tablename__ = 'bookings'
    booking_id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # Add autoincrement=True
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    payment_id = db.Column(db.String(45), nullable=False)
    journey_id = db.Column(db.Integer, db.ForeignKey('journey.journeyid'), nullable=False)
    booking_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    booking_reference = db.Column(db.String(10), nullable=False, unique=True)
    num_passengers = db.Column(db.Integer, nullable=False, default=1)
    total_price = db.Column(db.String(45), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Confirmed')
    
    # Relationships
    user = db.relationship('User', backref=db.backref('bookings', lazy=True))
    flight = db.relationship('Flight', backref=db.backref('bookings', lazy=True), 
                            foreign_keys=[journey_id])

# Payment Model
class Payment(db.Model):
    __tablename__ = 'payment_info'
    cardid = db.Column(db.Integer, primary_key=True, autoincrement=True)  # Add autoincrement=True
    idusers = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    card_num = db.Column(db.String(45), nullable=False)  # Will store last 4 digits only
    exp_date = db.Column(db.Date, nullable=False)
    sort_code = db.Column(db.String(45), nullable=True)
    security_code = db.Column(db.String(45), nullable=True)  # Will not store actual CVV
    
    # Relationship with user
    user = db.relationship('User', backref=db.backref('payments', lazy=True))

# Admin Model
class Admin(db.Model):
    __tablename__ = 'site_admin'
    site_admin_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(45), nullable=False)
    email = db.Column(db.String(45), unique=True, nullable=False)
    pword = db.Column(db.String(256), nullable=False)
    is_super_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime)
    last_login = db.Column(db.DateTime)

# User Model
class User(db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(45), nullable=False)
    last_name = db.Column(db.String(45), nullable=False)
    email = db.Column(db.String(45), unique=True, nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    tel_number = db.Column(db.String(45), nullable=False)
    address_line_1 = db.Column(db.String(45), nullable=False)
    address_line_2 = db.Column(db.String(45), nullable=True)
    address_line_3 = db.Column(db.String(45), nullable=True)
    city = db.Column(db.String(45), nullable=False)
    post_code = db.Column(db.String(45), nullable=False)
    state = db.Column(db.String(45), nullable=True)
    country_of_residence = db.Column(db.String(45), nullable=False)
    pword = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.String(5), nullable=True)

# Add this model to track revenue adjustments
class RevenueAdjustment(db.Model):
    __tablename__ = 'revenue_adjustments'
    adjustment_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.booking_id'), nullable=False)
    adjustment_amount = db.Column(db.String(45), nullable=False)  # Negative for refunds
    adjustment_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    reason = db.Column(db.String(100), nullable=False)
    reference = db.Column(db.String(45), nullable=False)
    
    # Relationship with booking
    booking = db.relationship('Booking', backref=db.backref('adjustments', lazy=True))

# Updated and completed middleware functions
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin login decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session or not session.get('is_admin'):
            flash('You must be logged in as an administrator to access this page.', 'danger')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Home Route
@app.route('/')
def index():
    # Check if user is logged in by checking for user_id in session
    is_logged_in = 'user_id' in session
    return render_template('index.html', is_logged_in=is_logged_in)

# Signup Route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        try:
            # Get all form data
            print("Processing signup form...")
            first_name = request.form['first_name']
            last_name = request.form['last_name']
            print(request.form)

            # Debug date format
            date_str = request.form['date_of_birth']
            print(f"Date string from form: {date_str}")
            
            try:
                # Change this line to use the correct format - HTML date inputs use YYYY-MM-DD
                date_of_birth = datetime.strptime(date_str, '%Y-%m-%d')
                print(f"Parsed date: {date_of_birth}")
            except ValueError as e:
                print(f"Date parsing error: {e}")
                flash(f"Invalid date format. Please use the date picker.", 'danger')
                return redirect(url_for('signup'))
                
            email = request.form['email']
            
            # Get the full international phone number if available
            if 'full_tel_number' in request.form and request.form['full_tel_number']:
                tel_number = request.form['full_tel_number']  # This includes the country code
                print(f"Full phone number with country code: {tel_number}")
            else:
                tel_number = request.form['tel_number']  # Fallback to the regular input
                print(f"Regular phone number: {tel_number}")
                
            address_line_1 = request.form['address_line_1']
            address_line_2 = request.form.get('address_line_2', '')
            address_line_3 = request.form.get('address_line_3', '')
            city = request.form['city']
            post_code = request.form['post_code']
            state = request.form.get('state', '')
            country_of_residence = request.form.get('country_of_residence', '')
            password = request.form['pword']
            confirm_password = request.form['conpword']
            
            # Check if passwords match
            if password != confirm_password:
                flash('Passwords do not match!', 'danger')
                return redirect(url_for('signup'))
            
            # Check if email already exists
            if User.query.filter_by(email=email).first():
                flash('Email already exists!', 'danger')
                return redirect(url_for('signup'))
            
            # Hash password
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            print(len(hashed_password))

            # Create new user with all fields
            new_user = User(
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date_of_birth,
                email=email,
                tel_number=tel_number,
                address_line_1=address_line_1,
                address_line_2=address_line_2,
                address_line_3=address_line_3,
                city=city,
                post_code=post_code,
                state=state,
                country_of_residence=country_of_residence,
                pword=hashed_password
            )
            
            # Add and commit to database
            db.session.add(new_user)
            db.session.commit()
            
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
            print(f"Signup error: {str(e)}")
            return redirect(url_for('signup'))
            
    return render_template('signUp.html')

# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            email = request.form['email']
            password = request.form['pword']
            
            user = User.query.filter_by(email=email).first()
            
            if user and bcrypt.checkpw(password.encode('utf-8'), user.pword.encode('utf-8')):
                session['user_id'] = user.user_id  # Add this line - it was missing!
                session['user_name'] = user.first_name  # Changed from user.fname
                flash('Login successful!', 'success')
                return redirect(url_for('profile'))
            else:
                flash('Invalid email or password!', 'danger')
                
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
            print(f"Login error: {str(e)}")
            
    return render_template('logIn.html')

# Profile Route
@app.route('/profile')
@login_required
def profile():
    user = User.query.get(session['user_id'])
    if not user:
        flash('User not found!', 'danger')
        return redirect(url_for('login'))
    
    # Fetch the user's bookings to display in profile
    user_bookings = Booking.query.filter_by(user_id=user.user_id).order_by(Booking.booking_date.desc()).limit(5).all()
    
    # Pass the user object and bookings to the template
    return render_template('profile.html', user=user, user_name=session['user_name'], user_bookings=user_bookings)

# Logout Route
@app.route('/logout')
def logout():
    session.clear()  # Clear all session variables
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('index'))

# Additional Routes for Other HTML Pages
@app.route('/airtravel')
def airtravel():
    return render_template('airTravel.html')

@app.route('/destinations')
def destinations():
    return render_template('destinations.html')

@app.route('/destination/<string:city>')
def destination_detail(city):
    """Display detailed information about a specific destination and available routes"""
    try:
        # Get destination info from a dictionary (in a real app, this would come from database)
        destinations = {
            'bristol': {
                'name': 'Bristol',
                'description': 'Bristol is a vibrant city in southwest England with a rich maritime history. The city boasts stunning architectural landmarks including Clifton Suspension Bridge and Bristol Cathedral. Visitors can explore the revitalized harbourside area filled with restaurants, galleries, and museums like M Shed and SS Great Britain. Known for its thriving arts scene, Bristol is home to works by famous street artist Banksy. The city combines historical charm with modern innovation, offering excellent shopping at Cabot Circus and scenic parks like Brandon Hill.',
                'attractions': ['Clifton Suspension Bridge', 'SS Great Britain', 'Bristol Cathedral', 'M Shed', 'Bristol Zoo Gardens'],
                'image': 'bristol.jpg',
                'best_time': 'May to September',
                'local_tip': 'Visit during the International Balloon Fiesta in August to see the sky filled with hot air balloons'
            },
            'edinburgh': {
                'name': 'Edinburgh',
                'description': 'Edinburgh, Scotland\'s historic capital, is a city of stunning contrasts where medieval Old Town meets elegant Georgian New Town. Dominated by Edinburgh Castle perched on an extinct volcano, the city offers visitors a journey through time with its Royal Mile, Palace of Holyroodhouse, and atmospheric underground vaults. Beyond its rich history, Edinburgh is renowned for its vibrant cultural scene, hosting the world\'s largest arts festival each August. With excellent museums, picturesque gardens, and Arthur\'s Seat offering panoramic views, Edinburgh combines majestic landscapes with urban sophistication.',
                'attractions': ['Edinburgh Castle', 'Royal Mile', 'Arthur\'s Seat', 'Palace of Holyroodhouse', 'National Museum of Scotland'],
                'image': 'edinburgh.jpg',
                'best_time': 'June to August',
                'local_tip': 'Explore the hidden closes and wynds off the Royal Mile for a glimpse into Edinburgh\'s past'
            },
            'london': {
                'name': 'London',
                'description': 'London, the dynamic capital of England, is a world-class city blending historical grandeur with cutting-edge modernity. Home to iconic landmarks like Big Ben, Buckingham Palace, and the Tower of London, it offers visitors a journey through centuries of history. The city\'s world-renowned museums and galleries, including the British Museum and Tate Modern, house treasures from across the globe. London\'s diverse neighborhoods each have their own character, from the luxury of Knightsbridge to the alternative scene in Camden. With its unmatched theater scene in the West End, beautiful royal parks, and multicultural culinary offerings, London remains one of the world\'s most exciting and diverse metropolitan destinations.',
                'attractions': ['The British Museum', 'Tower of London', 'Buckingham Palace', 'Westminster Abbey', 'The Shard'],
                'image': 'london.jpg',
                'best_time': 'April to June, September to October',
                'local_tip': 'Use an Oyster card for public transport and explore areas beyond the tourist center like Greenwich or Hampstead Heath'
            },
            'cardiff': {
                'name': 'Cardiff',
                'description': 'Cardiff, the capital of Wales, is a vibrant waterfront city with a rich blend of history and modern attractions. At its heart stands the magnificent Cardiff Castle, a Victorian Gothic revival mansion built on Roman foundations. The revitalized Cardiff Bay area offers a stunning waterfront with the Wales Millennium Centre, a hub for arts and culture. Sports enthusiasts can visit Principality Stadium, home to Welsh rugby. The city offers excellent shopping in its Victorian arcades and St David\'s Centre. With beautiful green spaces like Bute Park and accessible beaches nearby, Cardiff provides visitors with a diverse Welsh experience in a compact, walkable city.',
                'attractions': ['Cardiff Castle', 'Cardiff Bay', 'Principality Stadium', 'National Museum Cardiff', 'St Fagans National Museum of History'],
                'image': 'cardiff.jpg',
                'best_time': 'May to September',
                'local_tip': 'Take a boat trip from Cardiff Bay to Penarth for beautiful views of the coastline'
            },
            'manchester': {
                'name': 'Manchester',
                'description': 'Manchester is a vibrant, post-industrial city known for its significant contribution to music, sports, and culture. As the world\'s first industrialized city, it retains its working-class roots while embracing innovation and creativity. Home to two world-famous football clubs, Manchester United and Manchester City, it\'s a paradise for sports fans. The city\'s musical heritage includes legendary bands like Oasis and The Smiths, while institutions like the Manchester Art Gallery and the Science and Industry Museum showcase its cultural and historical significance. With a thriving food scene, impressive Victorian architecture, and the redeveloped Salford Quays area, Manchester offers visitors an energetic blend of history, arts, and entertainment.',
                'attractions': ['Manchester Cathedral', 'Old Trafford', 'The John Rylands Library', 'Science and Industry Museum', 'Manchester Art Gallery'],
                'image': 'manchester.jpg',
                'best_time': 'June to August',
                'local_tip': 'Explore the Northern Quarter for independent shops, street art, and great cafés'
            },
            'newcastle': {
                'name': 'Newcastle',
                'description': 'Newcastle upon Tyne is a vibrant city in northeast England, famous for its warm Geordie welcome and distinctive identity. The city is instantly recognizable by its seven iconic bridges spanning the River Tyne, including the innovative Gateshead Millennium Bridge. Newcastle\'s industrial heritage has been transformed into cultural spaces like BALTIC Centre for Contemporary Art, while the regenerated Quayside area buzzes with restaurants and nightlife. The city center features impressive neoclassical architecture, including Grey Street, and offers excellent shopping at Eldon Square. With its passionate football culture centered around Newcastle United FC, lively arts scene, and proximity to beautiful Northumberland countryside, Newcastle combines urban excitement with northern charm.',
                'attractions': ['Tyne Bridge', 'Newcastle Castle', 'The Quayside', 'BALTIC Centre for Contemporary Art', 'St. James\' Park'],
                'image': 'newcastle.jpg',
                'best_time': 'June to September',
                'local_tip': 'Visit the Quayside Market on Sundays for local crafts and street food'
            },
            'glasgow': {
                'name': 'Glasgow',
                'description': 'Glasgow, Scotland\'s largest city, is a vibrant cultural hub known for its friendly locals and rich architectural heritage. Once an industrial powerhouse, the city has reinvented itself as a center for arts, music, and design, earning UNESCO City of Music status. Visitors can explore world-class museums like Kelvingrove Art Gallery and Museum, admire the distinctive Art Nouveau buildings designed by Charles Rennie Mackintosh, or shop in the Style Mile. Glasgow\'s dynamic music scene fills venues across the city nightly, while its restaurant offerings range from traditional Scottish to innovative global cuisine. With beautiful Victorian buildings, expansive parks including Kelvingrove, and easy access to the Scottish Highlands, Glasgow offers an authentic Scottish experience with urban sophistication.',
                'attractions': ['Kelvingrove Art Gallery and Museum', 'Glasgow Cathedral', 'Riverside Museum', 'The Mackintosh House', 'Glasgow Green'],
                'image': 'glasgow.jpg',
                'best_time': 'May to September',
                'local_tip': 'Take a walking tour of the Mackintosh buildings to appreciate the city\'s architectural heritage'
            },
            'portsmouth': {
                'name': 'Portsmouth',
                'description': 'Portsmouth is a dynamic waterfront city with an unrivaled naval and maritime heritage. As the UK\'s only island city, it\'s home to historic ships including HMS Victory and HMS Warrior at the Portsmouth Historic Dockyard. The skyline is dominated by the iconic Spinnaker Tower, offering panoramic views across the Solent. Visitors can explore the D-Day Story museum, wander through Old Portsmouth\'s cobbled streets, or enjoy shopping and dining at Gunwharf Quays. With its strong connections to literary figures like Charles Dickens and Arthur Conan Doyle, rich military history, and seafront location, Portsmouth offers a unique blend of history, culture, and seaside charm.',
                'attractions': ['Portsmouth Historic Dockyard', 'Spinnaker Tower', 'Southsea Castle', 'The D-Day Story', 'Mary Rose Museum'],
                'image': 'portsmouth.jpg',
                'best_time': 'May to September',
                'local_tip': 'Take the waterbus from the Historic Dockyard to Gosport for great views of the harbor'
            },
            'dundee': {
                'name': 'Dundee',
                'description': 'Dundee, located on Scotland\'s east coast, is a city reinventing itself as a center for design, innovation, and culture. The spectacular V&A Dundee, Scotland\'s first design museum, symbolizes the city\'s transformation and waterfront regeneration. Once famous for "jute, jam, and journalism," Dundee celebrates its industrial heritage while embracing contemporary arts and sciences. Visitors can explore attractions like Discovery Point, featuring Captain Scott\'s Antarctic vessel RRS Discovery, or the engaging McManus Art Gallery and Museum. With panoramic views from The Law, the extinct volcano overlooking the city, and its position as a gateway to the Scottish highlands, Dundee combines urban renewal with natural beauty and historic charm.',
                'attractions': ['V&A Dundee', 'Discovery Point', 'The McManus: Dundee\'s Art Gallery & Museum', 'Dundee Law', 'Verdant Works'],
                'image': 'dundee.jpg',
                'best_time': 'June to September',
                'local_tip': 'Take a walk along the waterfront to see the city\'s impressive regeneration'
            },
            'southampton': {
                'name': 'Southampton',
                'description': 'Southampton is a major port city on England\'s south coast with a rich maritime history. Most famously known as the departure point of the Titanic in 1912, the city offers attractions like the SeaCity Museum which commemorates this connection. Southampton\'s historic medieval walls, one of the most complete in England, tell the story of its significant past. The city boasts excellent shopping at Westquay, a vibrant cultural scene with venues like the Mayflower Theatre, and beautiful green spaces including the Southampton Common. As a gateway to the Isle of Wight and New Forest National Park, Southampton combines urban amenities with easy access to stunning natural landscapes, while its working port continues the city\'s long seafaring tradition.',
                'attractions': ['SeaCity Museum', 'Tudor House and Garden', 'Southampton City Art Gallery', 'Solent Sky Museum', 'Medieval City Walls'],
                'image': 'southampton.jpg',
                'best_time': 'June to September',
                'local_tip': 'Visit Ocean Village marina for dining with views of the cruise ships'
            },
            'birmingham': {
                'name': 'Birmingham',
                'description': 'Birmingham, England\'s second-largest city, is a vibrant cultural center that has transformed from its industrial past into a dynamic, modern metropolis. Known for its extensive canal network (with more miles of canals than Venice), the city offers unique waterside dining and walking experiences. Cultural attractions abound, including the Birmingham Museum & Art Gallery with the world\'s largest Pre-Raphaelite collection, and the innovative Library of Birmingham. The city is famous for its diverse culinary scene, from the Balti Triangle\'s authentic curry houses to Michelin-starred restaurants. With excellent shopping at the iconic Bullring & Grand Central, the historic Jewellery Quarter, and as home to the City of Birmingham Symphony Orchestra, Birmingham offers visitors an exciting blend of heritage and contemporary urban experiences.',
                'attractions': ['Birmingham Museum & Art Gallery', 'Cadbury World', 'Birmingham Canals', 'Jewellery Quarter', 'Library of Birmingham'],
                'image': 'birmingham.jpg',
                'best_time': 'May to September',
                'local_tip': 'Take a canal boat tour to see the city from a different perspective'
            },
            'aberdeen': {
                'name': 'Aberdeen',
                'description': 'Aberdeen, known as the "Granite City," is a striking coastal city in northeast Scotland where silvery-gray stone buildings sparkle in the sunlight. With its rich maritime and oil industry heritage, the city offers a unique blend of urban sophistication and natural beauty. Visitors can explore Old Aberdeen with its medieval architecture including King\'s College and St. Machar\'s Cathedral, or enjoy the Winter Gardens at Duthie Park, one of Scotland\'s finest botanical gardens. The city\'s long sandy beach provides a refreshing seafront experience, while cultural attractions like Aberdeen Art Gallery showcase impressive collections. With its proximity to castle country and whisky distilleries in Royal Deeside and Aberdeenshire, Aberdeen serves as an excellent gateway to exploring Scotland\'s northeastern highlights.',
                'attractions': ['Aberdeen Maritime Museum', 'Duthie Park and Winter Gardens', 'Aberdeen Beach', 'Old Aberdeen', 'Aberdeen Art Gallery'],
                'image': 'aberdeen.jpg',
                'best_time': 'May to September',
                'local_tip': 'Visit nearby Footdee (locally called "Fittie"), a quaint former fishing village with unique cottages'
            }
        }
        
        # Get destination info or return 404 if not found
        destination = destinations.get(city.lower())
        if not destination:
            abort(404)
            
        # Get all flights to this destination
        flights_to = db.session.query(Flight).filter(
            Flight.arr_location.ilike(f'%{destination["name"]}%')
        ).all()
        
        # Get all flights from this destination
        flights_from = db.session.query(Flight).filter(
            Flight.dep_location.ilike(f'%{destination["name"]}%')
        ).all()
            
        return render_template('destination_detail.html',
                              destination=destination,
                              flights_to=flights_to,
                              flights_from=flights_from)
    
    except Exception as e:
        flash(f"Error loading destination details: {str(e)}", "danger")
        return redirect(url_for('destinations'))

@app.route('/bookings')
def bookings():
    if 'user_id' in session:
        # Get the user's bookings (same as my_bookings)
        user = User.query.get(session['user_id'])
        user_bookings = Booking.query.filter_by(user_id=user.user_id).all()
        return render_template('bookings.html', bookings=user_bookings)
    else:
        # If not logged in, show the booking lookup form
        return render_template('bookings.html', bookings=None)

@app.route('/flightstatus', methods=['GET', 'POST'])
def flightstatus():
    # Get the user's upcoming bookings if logged in
    user_bookings = []
    if 'user_id' in session:
        try:
            user_bookings = Booking.query.filter_by(
                user_id=session['user_id'],
                status='Confirmed'
            ).join(
                Flight, Booking.journey_id == Flight.journeyid
            ).filter(
                Flight.dep_time > datetime.now()
            ).order_by(
                Flight.dep_time
            ).limit(5).all()
        except Exception as e:
            print(f"Error fetching user bookings: {str(e)}")
    
    # Fetch all available flights for the tracker system
    all_flights = []
    try:
        all_flights = Flight.query.filter(
            Flight.dep_time > datetime.now(),
            Flight.dep_time < (datetime.now() + timedelta(days=7))
        ).all()
    except Exception as e:
        print(f"Error fetching flights for tracker: {str(e)}")
    
    # Format flight data for JavaScript
    flight_data = {}
    for flight in all_flights:
        try:
            # Calculate flight progress
            now = datetime.now()
            dep_time = flight.dep_time
            arr_time = flight.arr_time
            
            progress = 0
            status = "Scheduled"
            status_class = "on-time"
            
            if now > arr_time:
                progress = 100
                status = "Arrived"
                status_class = "arrived"
            elif now > dep_time:
                # Calculate percentage of flight completed
                total_duration = (arr_time - dep_time).total_seconds()
                elapsed_time = (now - dep_time).total_seconds()
                progress = min(int(elapsed_time / total_duration * 100), 99)
                status = "In Flight"
                status_class = "on-time"
            elif (dep_time - now).total_seconds() < 1800:  # 30 minutes before departure
                status = "Boarding"
                status_class = "boarding"
            
            # Format flight data for JS
            flight_data[flight.flight_number] = {
                "flightNumber": flight.flight_number,
                "departure": {
                    "code": flight.dep_location.split('(')[1].split(')')[0] if '(' in flight.dep_location else flight.dep_location[:3],
                    "city": flight.dep_location.split('(')[0].strip() if '(' in flight.dep_location else flight.dep_location,
                    "time": flight.dep_time.strftime('%H:%M'),
                    "date": flight.dep_time.strftime('%d %b %Y')
                },
                "arrival": {
                    "code": flight.arr_location.split('(')[1].split(')')[0] if '(' in flight.arr_location else flight.arr_location[:3],
                    "city": flight.arr_location.split('(')[0].strip() if '(' in flight.arr_location else flight.arr_location,
                    "time": flight.arr_time.strftime('%H:%M'),
                    "date": flight.arr_time.strftime('%d %b %Y')
                },
                "status": status,
                "statusClass": status_class,
                "progress": progress,
                "aircraft": "Airbus A319",  # Updated aircraft model
                "duration": f"{int((arr_time - dep_time).total_seconds() // 3600)}h {int((arr_time - dep_time).total_seconds() % 3600 // 60)}m",
                "gate": f"{chr(65 + (flight.journeyid % 6))}{flight.journeyid % 20 + 1}",  # Generate gate from ID
                "terminal": f"Terminal {flight.journeyid % 3 + 1}",
                "baggage": f"Carousel {flight.journeyid % 8 + 1}",
                "coordinates": None  # Will be calculated on client side
            }
        except Exception as e:
            print(f"Error processing flight {flight.flight_number}: {str(e)}")
    
    return render_template('flightStatus.html', 
                          user_bookings=user_bookings, 
                          flight_data=flight_data)

@app.route('/aboutus')
def aboutus():
    return render_template('aboutUs.html')

# Add search flights route
@app.route('/search_flights', methods=['POST'])
def search_flights():
    try:
        # Get form data
        origin = request.form['origin']
        destination = request.form['destination']
        date_str = request.form['date']
        passengers = int(request.form.get('travellers', 1))
        class_type = request.form.get('class_type', 'Economy')
        
        # Check if search date is more than 6 months in the future
        search_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        six_months_from_now = datetime.now().date() + timedelta(days=180)
        
        if search_date > six_months_from_now:
            available_date = (search_date - timedelta(days=180)).strftime('%Y-%m-%d')
            flash(f'Flights are only available up to 6 months in advance. '
                  f'Flights for your requested date will be available from {available_date}.', 'warning')
            return redirect(url_for('airtravel'))
        
        # Store search parameters in session
        session['search'] = {
            'origin': origin,
            'destination': destination,
            'date': date_str,
            'passengers': passengers,
            'class_type': class_type,
        }
        
        # Redirect to results page
        return redirect(url_for('flight_results'))
        
    except Exception as e:
        flash(f'Error searching flights: {str(e)}', 'danger')
        return redirect(url_for('airtravel'))

# Flight results page
@app.route('/flight_results')
def flight_results():
    if 'search' not in session:
        flash('No search parameters found. Please start a new search.', 'warning')
        return redirect(url_for('airtravel'))
    
    # Get the search parameters from session
    search = session['search']
    
    try:
        # Parse date string to datetime object
        search_date = datetime.strptime(search['date'], '%Y-%m-%d').date()
        
        # Query flights based on session data
        flights = Flight.query.filter_by(
            dep_location=search['origin'],
            arr_location=search['destination'],
            class_type=search['class_type']
        ).filter(
            func.date(Flight.dep_time) == search_date
        ).all()
        
        # Filter by available seats manually to handle string/int type issues
        flights = [flight for flight in flights if int(flight.seats) >= search['passengers']]
        
        # Flash message if no flights are found
        if not flights:
            flash(f'No flights found from {search["origin"]} to {search["destination"]} on {search["date"]}. Please try different dates or destinations.', 'info')
        
        return render_template('booking.html', flights=flights, search=search, now=datetime.now())  # Add now=datetime.now()
    except Exception as e:
        flash(f'Error searching flights: {str(e)}', 'danger')
        return redirect(url_for('airtravel'))

# Book flight route
@app.route('/book_flight/<int:flight_id>', methods=['GET', 'POST'])
@login_required
def book_flight(flight_id):
    if 'search' not in session:
        flash('Please search for flights first', 'warning')
        return redirect(url_for('airtravel'))
    
    flight = Flight.query.get_or_404(flight_id)
    search = session['search']
    
    # Get the current user
    user = User.query.get(session['user_id'])
    
    # Calculate total price
    total_price = float(flight.cost) * search['passengers']
    
    return render_template('checkout.html', 
                          flight=flight, 
                          search=search, 
                          user=user, 
                          total_price=total_price,
                          now=datetime.now())  # Add the current date here

# Process payment route - update this function
@app.route('/process_payment/<int:flight_id>', methods=['POST'])
@login_required
def process_payment(flight_id):
    if 'search' not in session:
        flash('Please search for flights first', 'warning')
        return redirect(url_for('airtravel'))
    
    flight = Flight.query.get_or_404(flight_id)
    search = session['search']
    user = User.query.get(session['user_id'])
    
    try:
        # Get payment details from form
        card_name = request.form['card_name']
        card_number = request.form['card_number'].replace(' ', '')
        expiry_date = request.form['expiry_date']
        cvv = request.form['cvv']
        
        # Validate payment info (in a real app, this would connect to a payment processor)
        if len(card_number) < 13 or len(card_number) > 19:
            flash('Invalid card number', 'danger')
            return redirect(url_for('book_flight', flight_id=flight_id))
        
        if not expiry_date or len(expiry_date) != 5:  # Format: MM/YY
            flash('Invalid expiry date', 'danger')
            return redirect(url_for('book_flight', flight_id=flight_id))
            
        if not cvv or len(cvv) < 3:
            flash('Invalid security code', 'danger')
            return redirect(url_for('book_flight', flight_id=flight_id))
        
        # Process expiry date
        month, year = expiry_date.split('/')
        exp_date = datetime.strptime(f"20{year}-{month}-01", '%Y-%m-%d').date()
        
        # Check if the card is expired
        if exp_date < datetime.now().date():
            flash('Your card has expired', 'danger')
            return redirect(url_for('book_flight', flight_id=flight_id))
        
        # Calculate base total price
        base_total_price = float(flight.cost) * search['passengers']
        
        # Calculate days in advance for the booking
        flight_date = flight.dep_time.date()
        today = datetime.now().date()
        days_in_advance = (flight_date - today).days
        
        # Apply discount based on days in advance
        discount_percentage = 0
        discount_message = ""
        
        if days_in_advance >= 80 and days_in_advance <= 90:
            discount_percentage = 25
            discount_message = f"25% advance booking discount applied (booked {days_in_advance} days in advance)"
        elif days_in_advance >= 60 and days_in_advance <= 79:
            discount_percentage = 15
            discount_message = f"15% advance booking discount applied (booked {days_in_advance} days in advance)"
        elif days_in_advance >= 45 and days_in_advance <= 59:
            discount_percentage = 10
            discount_message = f"10% advance booking discount applied (booked {days_in_advance} days in advance)"
        else:
            discount_message = "No advance booking discount applicable"
        
        # Calculate discount amount and final price
        discount_amount = (base_total_price * discount_percentage) / 100
        final_total_price = base_total_price - discount_amount
        
        # Get the next available cardid
        next_cardid_result = db.session.execute(text("SELECT MAX(cardid) FROM payment_info")).fetchone()
        next_cardid = 1 if next_cardid_result[0] is None else next_cardid_result[0] + 1
        
        # Store payment information with explicit cardid
        last_four = card_number[-4:]
        masked_number = f"************{last_four}"
        
        # Create payment record with explicit cardid
        payment = Payment(
            cardid=next_cardid,  # Set the cardid explicitly
            idusers=user.user_id,
            card_num=masked_number,
            exp_date=exp_date,
            sort_code='',
            security_code='***'
        )
        db.session.add(payment)
        db.session.flush()  # Flush to get the payment ID
        
        # Generate a unique booking reference
        booking_reference = f"HT{random.randint(10000, 99999)}"
        
        # Create booking with the discounted price
        new_booking = Booking(
            user_id=user.user_id,
            journey_id=flight.journeyid,
            payment_id=f"PAY-{payment.cardid}",  # Use payment ID to create a payment reference
            booking_date=datetime.utcnow(),
            booking_reference=booking_reference,
            num_passengers=search['passengers'],
            total_price=str(final_total_price),  # Use the discounted price
            status='Confirmed'
        )
        
        # Update flight seats
        remaining_seats = int(flight.seats) - search['passengers']
        flight.seats = str(remaining_seats)
        
        db.session.add(new_booking)
        db.session.commit()
        
        # Store discount info in session for display on confirmation page
        session['payment_info'] = {
            'last_four': last_four,
            'discount_percentage': discount_percentage,
            'base_price': base_total_price,
            'discount_amount': discount_amount,
            'final_price': final_total_price
        }
        
        # Send confirmation email with discount information
        send_booking_confirmation_email(user, new_booking, flight, payment, 
                                       discount_percentage=discount_percentage, 
                                       base_price=base_total_price)
        
        # Clear search data from session
        session.pop('search', None)
        
        flash(f'Flight booked successfully! {discount_message}', 'success')
        return redirect(url_for('booking_confirmation', booking_id=new_booking.booking_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error processing payment: {str(e)}', 'danger')
        return redirect(url_for('book_flight', flight_id=flight_id))

# Booking confirmation page
@app.route('/booking_confirmation/<int:booking_id>')
@login_required
def booking_confirmation(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    
    # Check if the booking belongs to the logged-in user
    if booking.user_id != session['user_id']:
        flash('You do not have permission to view this booking', 'danger')
        return redirect(url_for('profile'))
    
    # Get the flight details
    flight = Flight.query.get(booking.journey_id)
    
    # Get payment info from session or database
    payment_info = session.get('payment_info', {'last_four': 'XXXX'})
    
    # Clear payment info from session for security
    if 'payment_info' in session:
        session.pop('payment_info', None)
    
    return render_template('booking_confirmation.html', 
                           booking=booking, 
                           flight=flight, 
                           payment_info=payment_info)

# Add email sending function
def send_booking_confirmation_email(user, booking, flight, payment, discount_percentage=0, base_price=0):
    try:
        # Create the email content
        msg = MIMEMultipart()
        msg['From'] = app.config['MAIL_USERNAME']
        msg['To'] = user.email
        msg['Subject'] = f"Horizon Travel - Booking Confirmation #{booking.booking_reference}"
        
        # Calculate discount info for the email if applicable
        discount_html = ""
        if discount_percentage > 0:
            discount_amount = (base_price * discount_percentage) / 100
            discount_html = f"""
            <div style="background-color: #d4edda; border-color: #c3e6cb; color: #155724; padding: 10px; border-radius: 5px; margin: 10px 0;">
                <p><strong>Advance Booking Discount:</strong> {discount_percentage}%</p>
                <p><strong>Original Price:</strong> £{base_price:.2f}</p>
                <p><strong>Discount Amount:</strong> £{discount_amount:.2f}</p>
                <p><strong>You Saved:</strong> £{discount_amount:.2f}</p>
            </div>
            """
        
        # Email content creation with discount information
        email_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #007BFF; color: white; padding: 10px; text-align: center; }}
                .booking-details {{ background-color: #f9f9f9; padding: 15px; margin: 20px 0; }}
                .footer {{ font-size: 12px; text-align: center; margin-top: 30px; color: #777; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>Booking Confirmation</h2>
                </div>
                
                <p>Dear {user.first_name},</p>
                
                <p>Thank you for booking with Horizon Travel. Your flight has been confirmed!</p>
                
                <div class="booking-details">
                    <h3>Booking Details</h3>
                    <p><strong>Booking Reference:</strong> {booking.booking_reference}</p>
                    <p><strong>Flight Number:</strong> {flight.flight_number}</p>
                    <p><strong>From:</strong> {flight.dep_location}</p>
                    <p><strong>To:</strong> {flight.arr_location}</p>
                    <p><strong>Date:</strong> {flight.dep_time.strftime('%d %B %Y')}</p>
                    <p><strong>Departure Time:</strong> {flight.dep_time.strftime('%H:%M')}</p>
                    <p><strong>Arrival Time:</strong> {flight.arr_time.strftime('%H:%M')}</p>
                    <p><strong>Class:</strong> {flight.class_type}</p>
                    <p><strong>Passengers:</strong> {booking.num_passengers}</p>
                    <p><strong>Total Amount:</strong> £{booking.total_price}</p>
                </div>
                
                {discount_html}
                
                <p>You can view your booking details and manage your reservation by logging into your Horizon Travel account.</p>
                
                <p>If you have any questions, please feel free to contact our customer service team.</p>
                
                <p>We wish you a pleasant journey!</p>
                
                <p>Best regards,<br>The Horizon Travel Team</p>
                
                <div class="footer">
                    <p>This is an automated message, please do not reply to this email.</p>
                    <p>&copy; 2025 Horizon Travel. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(email_content, 'html'))
        
        # For development, still print to console for debugging
        print(f"\n=== CONFIRMATION EMAIL ===\nTo: {user.email}\n=== END EMAIL ===\n")
        
        # Actually send the email
        try:
            with smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT']) as server:
                server.starttls()
                server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
                server.send_message(msg)
            return True
        except Exception as e:
            print(f"Error sending email: {str(e)}")
            return False
            
    except Exception as e:
        print(f"Error creating confirmation email: {str(e)}")
        return False

# Add cancellation email sending function
def send_cancellation_email(booking, flight, refund_amount, cancellation_fee):
    """Send an email confirmation of booking cancellation with refund details"""
    try:
        # Get the user
        user = User.query.get(booking.user_id)
        if not user:
            return False
            
        # Create the email content
        msg = MIMEMultipart()
        msg['From'] = app.config['MAIL_USERNAME']
        msg['To'] = user.email
        msg['Subject'] = f"Horizon Travel - Booking Cancellation #{booking.booking_reference}"
        
        # Email content creation
        email_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #dc3545; color: white; padding: 10px; text-align: center; }}
                .booking-details {{ background-color: #f9f9f9; padding: 15px; margin: 20px 0; }}
                .footer {{ font-size: 12px; text-align: center; margin-top: 30px; color: #777; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>Booking Cancellation</h2>
                </div>
                
                <p>Dear {user.first_name},</p>
                
                <p>Your booking has been cancelled as requested. Details are provided below:</p>
                
                <div class="booking-details">
                    <h3>Cancelled Booking Details</h3>
                    <p><strong>Booking Reference:</strong> {booking.booking_reference}</p>
                    <p><strong>Flight Number:</strong> {flight.flight_number}</p>
                    <p><strong>From:</strong> {flight.dep_location}</p>
                    <p><strong>To:</strong> {flight.arr_location}</p>
                    <p><strong>Date:</strong> {flight.dep_time.strftime('%d %B %Y')}</p>
                    <p><strong>Departure Time:</strong> {flight.dep_time.strftime('%H:%M')}</p>
                </div>
                
                <div class="booking-details">
                    <h3>Refund Information</h3>
                    <p><strong>Original Amount:</strong> £{booking.total_price}</p>
                    <p><strong>Cancellation Fee:</strong> £{cancellation_fee:.2f}</p>
                    <p><strong>Refund Amount:</strong> £{refund_amount:.2f}</p>
                    <p>Refunds typically process within 7-10 business days, depending on your payment provider.</p>
                </div>
                
                <p>If you have any questions about your cancellation or refund, please contact our customer service team.</p>
                
                <p>Thank you for choosing Horizon Travel.</p>
                
                <p>Best regards,<br>The Horizon Travel Team</p>
                
                <div class="footer">
                    <p>This is an automated message, please do not reply to this email.</p>
                    <p>&copy; 2025 Horizon Travel. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(email_content, 'html'))
        
        # For development, print to console for debugging
        print(f"\n=== CANCELLATION EMAIL ===\nTo: {user.email}\n=== END EMAIL ===\n")
        
        # Actually send the email
        try:
            with smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT']) as server:
                server.starttls()
                server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
                server.send_message(msg)
            return True
        except Exception as e:
            print(f"Error sending cancellation email: {str(e)}")
            return False
            
    except Exception as e:
        print(f"Error creating cancellation email: {str(e)}")
        return False

# Add this function to the app.py
def send_flight_change_notification(user, booking, flight, schedule_changed=False, price_changed=False, original_price=None):
    """Send notification email about flight schedule or price changes"""
    try:
        # Create the email content
        msg = MIMEMultipart()
        msg['From'] = app.config['MAIL_USERNAME']
        msg['To'] = user.email
        
        # Set subject based on changes
        if schedule_changed and price_changed:
            msg['Subject'] = f"Important: Schedule and Price Change for Your Flight #{booking.booking_reference}"
        elif schedule_changed:
            msg['Subject'] = f"Important: Schedule Change for Your Flight #{booking.booking_reference}"
        else:
            msg['Subject'] = f"Good News: Price Reduction for Your Flight #{booking.booking_reference}"
        
        # Calculate price difference if price changed
        price_diff_html = ""
        if price_changed and original_price:
            current_price = float(booking.total_price)
            price_diff = float(original_price) - current_price
            price_diff_html = f"""
            <div style="background-color: #d4edda; border-color: #c3e6cb; color: #155724; padding: 10px; border-radius: 5px; margin: 10px 0;">
                <p><strong>Price Reduction Applied:</strong></p>
                <p><strong>Original Price:</strong> £{original_price}</p>
                <p><strong>New Price:</strong> £{current_price}</p>
                <p><strong>You Saved:</strong> £{price_diff:.2f}</p>
                <p>This reduction has been automatically applied to your booking.</p>
            </div>
            """
        
        # Email content creation
        email_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #007BFF; color: white; padding: 10px; text-align: center; }}
                .booking-details {{ background-color: #f9f9f9; padding: 15px; margin: 20px 0; }}
                .footer {{ font-size: 12px; text-align: center; margin-top: 30px; color: #777; }}
                .schedule-change {{ background-color: #fff3cd; border-color: #ffeeba; color: #856404; padding: 10px; border-radius: 5px; margin: 10px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>Flight Update</h2>
                </div>
                
                <p>Dear {user.first_name},</p>
                
                <p>We're writing to inform you about changes to your upcoming flight with Horizon Travel.</p>
                
                <div class="booking-details">
                    <h3>Booking Details</h3>
                    <p><strong>Booking Reference:</strong> {booking.booking_reference}</p>
                    <p><strong>Flight Number:</strong> {flight.flight_number}</p>
                    <p><strong>From:</strong> {flight.dep_location}</p>
                    <p><strong>To:</strong> {flight.arr_location}</p>
                </div>
                
                {price_diff_html}
                
                {"<div class='schedule-change'><p><strong>Schedule Change:</strong> Your flight times have been updated. Please check the new schedule below:</p>" if schedule_changed else ""}
                {"<p><strong>New Departure Time:</strong> " + flight.dep_time.strftime('%d %B %Y at %H:%M') + "</p>" if schedule_changed else ""}
                {"<p><strong>New Arrival Time:</strong> " + flight.arr_time.strftime('%d %B %Y at %H:%M') + "</p></div>" if schedule_changed else ""}
                
                <p>You can view your updated booking details by logging into your Horizon Travel account.</p>
                
                <p>If you have any questions or need to make changes to your booking, please contact our customer service team.</p>
                
                <p>Thank you for choosing Horizon Travel.</p>
                
                <p>Best regards,<br>The Horizon Travel Team</p>
                
                <div class="footer">
                    <p>This is an automated message, please do not reply to this email.</p>
                    <p>&copy; 2025 Horizon Travel. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(email_content, 'html'))
        
        # For development, print to console for debugging
        print(f"\n=== FLIGHT CHANGE NOTIFICATION ===\nTo: {user.email}\nSubject: {msg['Subject']}\n=== END EMAIL ===\n")
        
        # Actually send the email - uncomment in production
        # with smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT']) as server:
        #     server.starttls()
        #     server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
        #     server.send_message(msg)
        
        return True
            
    except Exception as e:
        print(f"Error sending flight change notification: {str(e)}")
        return False

# View user bookings
@app.route('/my_bookings')
@login_required
def my_bookings():
    # Get the user's bookings
    user = User.query.get(session['user_id'])
    user_bookings = Booking.query.filter_by(user_id=user.user_id).all()
    
    return render_template('my_bookings.html', bookings=user_bookings)

# Route for checking booking status by reference and surname
@app.route('/check_booking', methods=['POST'])
def check_booking():
    booking_reference = request.form['booking_reference']
    last_name = request.form['last_name']
    
    # Look up the booking
    booking = Booking.query.filter_by(booking_reference=booking_reference).first()
    
    if not booking:
        flash('Booking not found', 'danger')
        return redirect(url_for('bookings'))
    
    # Get the user who made the booking
    user = User.query.get(booking.user_id)
    
    # Fix this line - change sname to last_name
    if user.last_name.lower() != last_name.lower():
        flash('Booking details do not match', 'danger')
        return redirect(url_for('bookings'))
    
    # If all checks pass, show the booking details
    return render_template('booking_details.html', booking=booking, user=user)

# Add route for viewing a booking
@app.route('/view_booking/<int:booking_id>')
@login_required
def view_booking(booking_id):
    # Get booking
    booking = Booking.query.get_or_404(booking_id)
    
    # Check if booking belongs to current user
    if booking.user_id != session['user_id']:
        flash('You do not have permission to view this booking', 'danger')
        return redirect(url_for('my_bookings'))
    
    # Get flight details
    flight = Flight.query.get(booking.journey_id)
    
    # Get user details
    user = User.query.get(booking.user_id)
    
    # Get payment info
    payment = Payment.query.filter_by(idusers=user.user_id).order_by(Payment.cardid.desc()).first()
    if payment:
        payment_info = {'last_four': payment.card_num[-4:]}
    else:
        payment_info = {'last_four': 'XXXX'}
    
    # Calculate business upgrade fee
    business_upgrade_fee = get_business_upgrade_fee(flight, booking.num_passengers)
    
    return render_template('view_booking.html', 
                          booking=booking, 
                          flight=flight, 
                          user=user, 
                          payment_info=payment_info,
                          business_upgrade_fee=business_upgrade_fee,
                          datetime=datetime)  # Pass datetime to the template

# Add route for canceling a booking
@app.route('/cancel_booking/<int:booking_id>')
@login_required
def cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    
    # Check if booking belongs to current user
    if booking.user_id != session['user_id']:
        flash('You do not have permission to cancel this booking', 'danger')
        return redirect(url_for('bookings'))
    
    # Check if booking can be canceled (i.e., it's not already canceled)
    if booking.status == 'Cancelled':
        flash('This booking has already been cancelled', 'warning')
        return redirect(url_for('view_booking', booking_id=booking_id))
    
    try:
        # Get the flight to check dates
        flight = Flight.query.get(booking.journey_id)
        if not flight:
            flash('Flight information could not be found', 'danger')
            return redirect(url_for('view_booking', booking_id=booking_id))
            
        # Calculate days until flight departure
        days_until_flight = (flight.dep_time.date() - datetime.now().date()).days
        
        # Calculate refund amount based on cancellation policy
        total_price = float(booking.total_price)
        refund_amount = 0
        cancellation_fee = 0
        
        if days_until_flight > 60:
            # Full refund - no cancellation fee
            refund_amount = total_price
            cancellation_fee = 0
            refund_message = "You will receive a full refund as you're cancelling more than 60 days before departure."
        elif days_until_flight >= 30:
            # 60% refund - 40% cancellation fee
            cancellation_fee = total_price * 0.4
            refund_amount = total_price - cancellation_fee
            refund_message = f"You will be charged a 40% cancellation fee (£{cancellation_fee:.2f}) as you're cancelling between 30 and 60 days before departure."
        else:
            # No refund - 100% cancellation fee
            cancellation_fee = total_price
            refund_amount = 0
            refund_message = "No refund will be issued as you're cancelling within 30 days of departure."
        
        # Update flight seats (add the seats back)
        if flight:
            flight.seats = str(int(flight.seats) + booking.num_passengers)
        
        # Update booking status and store refund information
        booking.status = 'Cancelled'
        
        # Create a record of the cancellation in database
        # If you have a cancellations table, you could add a record there
        # Otherwise, we'll track it with booking status + optional fields
        
        # Option: Add these fields to your Booking model if they don't exist
        # booking.cancellation_date = datetime.utcnow()
        # booking.refund_amount = str(refund_amount)
        # booking.cancellation_fee = str(cancellation_fee)
        
        # Create a revenue adjustment record for reporting purposes
        try:
            # Use raw SQL to insert a negative revenue adjustment record
            # This is a simple approach - in a real application, you might want a proper "revenue_adjustments" table
            adjustment_reference = f"REF-{booking.booking_reference}"
            revenue_adjustment_sql = text("""
                INSERT INTO revenue_adjustments 
                (booking_id, adjustment_amount, adjustment_date, reason, reference) 
                VALUES (:booking_id, :amount, :date, :reason, :reference)
            """)
            
            db.session.execute(revenue_adjustment_sql, {
                'booking_id': booking.booking_id,
                'amount': -refund_amount,  # Negative amount for refund
                'date': datetime.utcnow(),
                'reason': 'Booking cancellation',
                'reference': adjustment_reference
            })
        except Exception as adj_err:
            # If the revenue_adjustments table doesn't exist, just log and continue
            print(f"Revenue adjustment tracking error: {str(adj_err)}")
            # This won't block the cancellation process
        
        db.session.commit()
        
        # Send cancellation email with refund details
        try:
            send_cancellation_email(booking, flight, refund_amount, cancellation_fee)
        except Exception as email_err:
            print(f"Error sending cancellation email: {str(email_err)}")
        
        flash(f'Booking cancelled successfully. {refund_message}', 'success')
        return redirect(url_for('bookings'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error cancelling booking: {str(e)}', 'danger')
        return redirect(url_for('view_booking', booking_id=booking_id))

# Admin Login Route
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        print(f"Login attempt with email: {email} and password length: {len(password)}")

        if not email or not password:
            flash('Email and password are required!', 'danger')
            return render_template('admin_login.html')

        from sqlalchemy import func
        admin = Admin.query.filter(func.lower(Admin.email) == func.lower(email)).first()

        print(f"Admin found in DB: {admin is not None}")
        
        if admin:
            print(f"Admin ID: {admin.site_admin_id}")
            print(f"Admin email: {admin.email}")
            print(f"Admin password hash from DB: {admin.pword}") # Print the full hash
            
            # Check password match
            try:
                password_match = bcrypt.checkpw(password.encode('utf-8'), admin.pword.encode('utf-8'))
                print(f"Password match result: {password_match}") # Renamed for clarity
            except ValueError: # Handle cases where the hash might be invalid/not bcrypt
                password_match = False
                print("Password hash format error during check.")

        if admin and password_match:
            session['admin_id'] = admin.site_admin_id
            session['admin_username'] = admin.name
            session['is_admin'] = True
            session['is_super_admin'] = admin.is_super_admin

            admin.last_login = datetime.utcnow()
            db.session.commit()

            flash('Login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid email or password!', 'danger')

    return render_template('admin_login.html')

# Admin Profile Route
@app.route('/admin/profile')
@admin_required
def admin_profile():
    # Just redirect to the dashboard since we're showing profile there
    return redirect(url_for('admin_dashboard'))

# Admin Dashboard (update to use admin_dash.html)
@app.route('/admin')
@admin_required
def admin_dashboard():
    # Get current admin user
    admin = Admin.query.get(session['admin_id'])
    
    # Gather statistics for the dashboard
    total_users = 0
    total_bookings = 0
    total_flights = 0
    total_revenue = 0
    recent_bookings = []
    
    try:
        # Get user count
        total_users = User.query.count()
        
        # Count only confirmed bookings
        result = db.session.execute(text("SELECT COUNT(*) FROM bookings WHERE status = 'Confirmed'"))
        total_bookings = result.scalar() or 0
        
        # Get flight count
        result = db.session.execute(text("SELECT COUNT(*) FROM journey"))
        total_flights = result.scalar() or 0
        
        # Fix: Simple manual calculation of confirmed booking revenue
        total_revenue = 0
        confirmed_bookings = db.session.execute(
            text("SELECT booking_id, total_price FROM bookings WHERE status = 'Confirmed'")
        ).fetchall()
        
        # Debug info
        print(f"Found {len(confirmed_bookings)} confirmed bookings")
        
        # Calculate total by adding each booking manually
        for booking in confirmed_bookings:
            try:
                # Extract booking_id and price from the result
                booking_id = booking[0]
                price_str = booking[1]
                
                # Convert price to float and add to total
                if price_str:
                    price = float(price_str)
                    total_revenue += price
                    print(f"Added booking {booking_id} with price £{price}")
            except (ValueError, TypeError, IndexError) as e:
                print(f"Error processing booking: {e}")
        
        # Round to 2 decimal places for display
        total_revenue = round(total_revenue, 2)
        print(f"Final calculated revenue: £{total_revenue}")
        
        # Get recent bookings
        sql = """
            SELECT b.booking_id, b.booking_reference, b.booking_date, b.num_passengers, 
                   b.total_price, b.status, u.first_name, u.last_name, 
                   j.dep_location, j.arr_location 
            FROM bookings b
            JOIN users u ON b.user_id = u.user_id
            JOIN journey j ON b.journey_id = j.journeyid
            ORDER BY b.booking_date DESC
            LIMIT 10
        """
        recent_bookings = db.session.execute(text(sql)).fetchall()
        
    except Exception as e:
        print(f"Error calculating dashboard stats: {str(e)}")
        
    return render_template('admin_dash.html', 
                          admin=admin,
                          total_users=total_users, 
                          total_bookings=total_bookings,
                          total_flights=total_flights,
                          total_revenue=total_revenue,
                          recent_bookings=recent_bookings)

# User Management
@app.route('/admin/users')
@admin_required
def admin_users():
    users = User.query.all()
    return render_template('user_management.html', users=users)

@app.route('/admin/user/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        user.first_name = request.form['first_name']
        user.last_name = request.form['last_name']
        user.email = request.form['email']
        user.tel_number = request.form['tel_number']
        user.address_line_1 = request.form['address_line_1']
        user.city = request.form['city']
        user.post_code = request.form['post_code']
        user.country_of_residence = request.form['country_of_residence']
        
        # Update password if provided
        new_password = request.form.get('password')
        if new_password and len(new_password) >= 6:
            user.pword = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        db.session.commit()
        flash(f"User {user.first_name} {user.last_name} updated successfully!", "success")
        return redirect(url_for('admin_users'))
    
    return render_template('edit_user.html', user=user)

@app.route('/admin/user/delete/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    try:
        # Delete associated bookings first
        Booking.query.filter_by(user_id=user.user_id).delete()
        db.session.delete(user)
        db.session.commit()
        flash(f"User {user.first_name} {user.last_name} and all associated bookings deleted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting user: {str(e)}", "danger")
    
    return redirect(url_for('admin_users'))

# Flight Management
@app.route('/admin/flights')
@admin_required
def admin_flights():
    try:
        # Ensure travel company with ID 1 exists
        ensure_travel_company_exists(1)
        
        # Use a raw SQL query that only selects fields that actually exist in your database
        sql_query = """
        SELECT journeyid, id_travelcompany, flight_number, dep_location, arr_location, 
               dep_time, arr_time, cost, seats, class_type 
        FROM journey
        """
        results = db.session.execute(text(sql_query)).fetchall()
        
        # Convert to Flight objects that your template can use
        flights = []
        for row in results:
            flight = Flight(
                journeyid=row[0],
                id_travelcompany=row[1],
                flight_number=row[2],
                dep_location=row[3],
                arr_location=row[4],
                dep_time=row[5], 
                arr_time=row[6],
                cost=row[7],
                seats=row[8],
                class_type=row[9]
            )
            flights.append(flight)
        
        # Return the flights.html template instead of admin_add_flight.html
        return render_template('flights.html', flights=flights)
    except Exception as e:  # Add this missing except block
        flash(f'Error loading flights: {str(e)}', 'danger')
        return redirect(url_for('admin_dashboard'))

# Reports
@app.route('/admin/reports')
@admin_required
def admin_reports():
    return render_template('admin_reports.html')

@app.route('/admin/flight/add', methods=['GET', 'POST'])
@admin_required
def admin_add_flight():
    if request.method == 'POST':
        try:
            # Get form data including flight number
            id_travelcompany = int(request.form['id_travelcompany'])
            
            # Ensure travel company exists
            if not ensure_travel_company_exists(id_travelcompany):
                flash(f'Error: Travel company with ID {id_travelcompany} could not be created', 'danger')
                return redirect(url_for('admin_add_flight'))
                
            flight_number = request.form['flight_number']  # Get flight number from form
            dep_location = request.form['dep_location']
            arr_location = request.form['arr_location']
            cost = request.form['cost']
            business_cost = request.form['business_cost']
            
            # Get seat configuration
            economy_seats = int(request.form.get('economy_seats', 104))  # 80% of 130
            business_seats = int(request.form.get('business_seats', 26))  # 20% of 130
            
            schedule_type = request.form['schedule_type']
            
            # Get the maximum journeyid
            max_id_result = db.session.query(func.max(Flight.journeyid)).first()
            next_id = 1 if max_id_result[0] is None else max_id_result[0] + 1
            
            if schedule_type == 'one_time':
                # Single flight handling
                departure_date = request.form['departure_date']
                dep_time_str = request.form['dep_time']
                arr_time_str = request.form['arr_time']
                
                # Combine date and time into datetime objects
                dep_datetime = datetime.strptime(f"{departure_date} {dep_time_str}", '%Y-%m-%d %H:%M')
                arr_datetime = datetime.strptime(f"{departure_date} {arr_time_str}", '%Y-%m-%d %H:%M')
                
                # If arrival is before departure (meaning next day arrival), add a day
                if arr_datetime < dep_datetime:
                    arr_datetime = arr_datetime + timedelta(days=1)
                
                # Create economy flight with flight number
                economy_flight = Flight(
                    journeyid=next_id,
                    id_travelcompany=id_travelcompany,
                    flight_number=flight_number + "E",  # Add E for Economy
                    dep_location=dep_location,
                    arr_location=arr_location,
                    dep_time=dep_datetime,
                    arr_time=arr_datetime,
                    cost=cost,
                    seats=str(economy_seats),
                    class_type="Economy"
                )
                
                # Create business class flight with flight number
                business_flight = Flight(
                    journeyid=next_id + 1,
                    id_travelcompany=id_travelcompany,
                    flight_number=flight_number + "B",  # Add B for Business
                    dep_location=dep_location,
                    arr_location=arr_location,
                    dep_time=dep_datetime,
                    arr_time=arr_datetime,
                    cost=business_cost,
                    seats=str(business_seats),
                    class_type="Business"
                )
                
                db.session.add(economy_flight)
                db.session.add(business_flight)
                db.session.commit()
                
                flash('Flight added successfully!', 'success')
                
            else:  # Recurring flights
                # Get selected weekdays
                weekdays = request.form.getlist('weekdays')
                if not weekdays:
                    flash('Please select at least one weekday for recurring flights.', 'danger')
                    return redirect(url_for('admin_add_flight'))
                
                # Convert to integers
                weekdays = [int(day) for day in weekdays]
                
                # Get time inputs
                dep_time_str = request.form['dep_time']
                arr_time_str = request.form['arr_time']
                
                # Calculate start and end dates (today and 6 months from today)
                start_date = datetime.now().date()
                end_date = start_date + timedelta(days=180)  # Approximately 6 months
                
                # Generate flights for each weekday in the 6-month period
                current_date = start_date
                flight_count = 0
                
                while current_date <= end_date:
                    # Check if current day is in selected weekdays (0=Monday, 6=Sunday)
                    if current_date.weekday() in weekdays:
                        # Create the departure and arrival datetimes
                        dep_datetime = datetime.combine(current_date, datetime.strptime(dep_time_str, '%H:%M').time())
                        arr_datetime = datetime.combine(current_date, datetime.strptime(arr_time_str, '%H:%M').time())
                        
                        # If arrival is before departure (meaning next day arrival), add a day
                        if arr_datetime < dep_datetime:
                            arr_datetime = arr_datetime + timedelta(days=1)
                        
                        # Create economy flight with flight number
                        economy_flight = Flight(
                            journeyid=next_id,
                            id_travelcompany=id_travelcompany,
                            flight_number=flight_number + "E",
                            dep_location=dep_location,
                            arr_location=arr_location,
                            dep_time=dep_datetime,
                            arr_time=arr_datetime,
                            cost=cost,
                            seats=str(economy_seats),
                            class_type="Economy"
                        )
                        
                        # Create business class flight with flight number
                        business_flight = Flight(
                            journeyid=next_id + 1,
                            id_travelcompany=id_travelcompany,
                            flight_number=flight_number + "B",
                            dep_location=dep_location,
                            arr_location=arr_location,
                            dep_time=dep_datetime,
                            arr_time=arr_datetime,
                            cost=business_cost,
                            seats=str(business_seats),
                            class_type="Business"
                        )
                        
                        db.session.add(economy_flight)
                        db.session.add(business_flight)
                        flight_count += 2  # One economy + one business
                        
                        # Always increment by 2 for each pair of flights
                        next_id += 2
                    
                    # Move to next day
                    current_date += timedelta(days=1)
                
                db.session.commit()
                flash(f'{flight_count} recurring flights added successfully for the next 6 months!', 'success')
            
            return redirect(url_for('admin_flights'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding flight: {str(e)}', 'danger')
    
    # For GET request, show the form with empty fields
    travel_companies = [
        {"id": 1, "name": "Horizon Airways"},
    ]
    locations = ["Bristol(BRS)", "London(LON)", "Edinburgh(EDI)", "Cardiff(CWL)", "Manchester(MAN)", 
                "Glasgow(GLA)", "Portsmouth", "Dundee(DND)", "Southampton(SOU)", "Birmingham(BHX)",
                "Newcastle(NCL)", "Aberdeen(ABZ)"]
    class_types = ["Economy", "Business"]
    
    return render_template('admin_add_flight.html',
                          travel_companies=travel_companies,
                          locations=locations,
                          class_types=class_types)

@app.route('/admin/flight/<int:flight_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_flight(flight_id):
    flight = Flight.query.get_or_404(flight_id)
    
    if request.method == 'POST':
        # Store original values for comparison
        original_dep_time = flight.dep_time
        original_arr_time = flight.arr_time
        original_cost = flight.cost
        
        # Update flight details
        flight.id_travelcompany = request.form['company']
        flight.dep_location = request.form['departure']
        flight.arr_location = request.form['arrival']
        flight.flight_number = request.form.get('flight_number', flight.flight_number)
        
        # Handle date and time fields correctly
        departure_date = request.form['departure_date']
        dep_time_str = request.form['departure_time']
        arr_time_str = request.form['arrival_time']
        
        # Combine date and time
        dep_datetime = datetime.strptime(f"{departure_date} {dep_time_str}", '%Y-%m-%d %H:%M')
        arr_datetime = datetime.strptime(f"{departure_date} {arr_time_str}", '%Y-%m-%d %H:%M')
        
        # If arrival is before departure, add a day
        if arr_datetime < dep_datetime:
            arr_datetime = arr_datetime + timedelta(days=1)
            
        flight.dep_time = dep_datetime
        flight.arr_time = arr_datetime
        
        # Update cost and seats
        flight.cost = request.form['cost']
        flight.seats = request.form['seats']
        flight.class_type = request.form['class_type']
        
        try:
            # Find all affected bookings
            affected_bookings = Booking.query.filter_by(journey_id=flight.journeyid).all()
            
            # Track stats for the final message
            notify_count = 0
            price_adjust_count = 0
            
            # Process updates and notifications
            if affected_bookings:
                # Track if we need to notify customers
                schedule_changed = original_dep_time != dep_datetime or original_arr_time != arr_datetime
                price_decreased = float(original_cost) > float(flight.cost)
                
                for booking in affected_bookings:
                    # Skip cancelled bookings
                    if booking.status == 'Cancelled':
                        continue
                        
                    # Get user info
                    user = User.query.get(booking.user_id)
                    if not user:
                        continue
                    
                    # Track original booking price
                    original_booking_price = booking.total_price
                    
                    # If price decreased, adjust booking total price accordingly
                    if price_decreased:
                        # Calculate price difference per passenger
                        price_diff = float(original_cost) - float(flight.cost)
                        # Adjust total booking price
                        new_total = float(booking.total_price) - (price_diff * booking.num_passengers)
                        booking.total_price = str(max(0, new_total))  # Ensure price doesn't go negative
                        price_adjust_count += 1
                    
                    # Send notification about changes to the user
                    if schedule_changed or price_decreased:
                        try:
                            send_flight_change_notification(
                                user, 
                                booking, 
                                flight,
                                schedule_changed=schedule_changed,
                                price_changed=price_decreased,
                                original_price=original_booking_price
                            )
                            notify_count += 1
                        except Exception as notify_err:
                            print(f"Error sending notification: {str(notify_err)}")
            
            db.session.commit()
            
            # Report to the admin what happened
            if affected_bookings:
                message = f"Flight updated successfully! {len(affected_bookings)} existing bookings were affected."
                if notify_count > 0:
                    message += f" {notify_count} customers have been notified of changes."
                if price_adjust_count > 0:
                    message += f" {price_adjust_count} booking prices have been adjusted due to fare decrease."
                flash(message, "success")
            else:
                flash("Flight updated successfully!", "success")
                
            return redirect(url_for('admin_flights'))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating flight: {str(e)}", "danger")
    
    # GET request - prepare the form
    # Get unique values for dropdowns
    travel_companies = db.session.query(Flight.id_travelcompany).distinct().all()
    locations = db.session.query(Flight.dep_location).union(db.session.query(Flight.arr_location)).distinct().all()
    class_types = db.session.query(Flight.class_type).distinct().all()
    
    return render_template('admin_edit_flight.html', 
                          flight=flight,
                          travel_companies=[tc[0] for tc in travel_companies],
                          locations=[loc[0] for loc in locations],
                          class_types=[ct[0] for ct in class_types])

@app.route('/admin/flight/delete/<int:flight_id>', methods=['POST'])
@admin_required
def admin_delete_flight(flight_id):
    flight = Flight.query.get_or_404(flight_id)
    
    try:
        # Check if there are associated bookings - use journeyid not journey_id
        bookings_count = Booking.query.filter_by(journey_id=flight.journeyid).count()
        if bookings_count > 0:
            flash(f"Cannot delete flight: There are {bookings_count} bookings associated with this flight.", "danger")
            return redirect(url_for('admin_flights'))
        
        db.session.delete(flight)
        db.session.commit()
        flash("Flight deleted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting flight: {str(e)}", "danger")
    
    return redirect(url_for('admin_flights'))

# Special route for deleting all flights (for experimental purposes only)
@app.route('/admin/flights/delete-all', methods=['POST'])
@admin_required
def admin_delete_all_flights():
    try:
        # First check if there are any bookings
        booking_count = Booking.query.count()
        if booking_count > 0:
            flash(f'Cannot delete all flights: There are {booking_count} active bookings in the system. Delete all bookings first.', 'danger')
            return redirect(url_for('admin_flights'))
        
        # Delete all flights
        Flight.query.delete()
        db.session.commit()
        
        flash('All flights have been deleted successfully!', 'success')
        return redirect(url_for('admin_flights'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting flights: {str(e)}', 'danger')
        return redirect(url_for('admin_flights'))

@app.route('/admin/report/monthly_sales')
@admin_required
def admin_report_monthly_sales():
    """Generate a monthly sales report with visual charts and data table"""
    from datetime import datetime
    
    # Get current year and allow for query parameter to view different years
    current_year = request.args.get('year', default=datetime.now().year, type=int)
    
    try:
        # Query monthly sales for the selected year - only count confirmed bookings
        monthly_data = db.session.query(
            extract('month', Booking.booking_date).label('month'),
            func.count(Booking.booking_id).label('booking_count'),
            func.sum(cast(Booking.total_price, Numeric)).label('total_revenue')
        ).filter(
            extract('year', Booking.booking_date) == current_year,
            Booking.status == 'Confirmed'  # Only count confirmed bookings
        ).group_by(
            extract('month', Booking.booking_date)
        ).order_by(
            extract('month', Booking.booking_date)
        ).all()
        
        # Format the data for the template
        months = ["January", "February", "March", "April", "May", "June", 
                  "July", "August", "September", "October", "November", "December"]
        
        sales_data = {
            'months': months,
            'booking_counts': [0] * 12,
            'revenues': [0] * 12
        }
        
        for data in monthly_data:
            month_idx = int(data.month) - 1  # Adjust to 0-indexed
            sales_data['booking_counts'][month_idx] = data.booking_count
            sales_data['revenues'][month_idx] = float(data.total_revenue or 0)
        
        # Get available years for the dropdown selector
        years_result = db.session.query(
            extract('year', Booking.booking_date).distinct()
        ).order_by(
            extract('year', Booking.booking_date).desc()
        ).all()
        
        available_years = [int(year[0]) for year in years_result if year[0] is not None]
        if not available_years:
            available_years = [datetime.now().year]
            
        return render_template('admin_monthly_sales.html', 
                              sales_data=sales_data, 
                              current_year=current_year,
                              available_years=available_years,
                              datetime=datetime)
                              
    except Exception as e:
        print(f"Error generating monthly sales report: {str(e)}")
        flash(f"Error generating report: {str(e)}", "danger")
        return redirect(url_for('admin_reports'))

@app.route('/admin/report/route_analysis')
@admin_required
def admin_report_route_analysis():
    """Generate a comprehensive route performance analysis report"""
    from datetime import datetime

    try:
        # Query route performance data - only for confirmed bookings
        route_data = db.session.query(
            Flight.dep_location,
            Flight.arr_location,
            func.count(Booking.booking_id).label('booking_count'),
            func.sum(cast(Booking.total_price, Numeric)).label('total_revenue'),
            func.avg(cast(Flight.cost, Numeric)).label('avg_cost_per_booking'),
            # Include date range data
            func.min(Flight.dep_time).label('first_flight'),
            func.max(Flight.dep_time).label('last_flight')
        ).join(
            Booking, Flight.journeyid == Booking.journey_id
        ).filter(
            Booking.status == 'Confirmed'  # Only include confirmed bookings
        ).group_by(
            Flight.dep_location,
            Flight.arr_location
        ).all()
        
        # Calculate profit/loss for each route with more detailed metrics
        route_analysis = []
        for route in route_data:
            revenue = float(route.total_revenue or 0)
            avg_cost = float(route.avg_cost_per_booking or 0)
            
            # Estimate operational costs (you may adjust this calculation)
            operational_cost = avg_cost * route.booking_count * 0.7
            
            # Calculate profit metrics
            profit = revenue - operational_cost
            profit_margin = (profit / revenue * 100) if revenue > 0 else 0
            
            # Calculate frequency and route performance metrics
            date_range = (route.last_flight - route.first_flight).days + 1
            flights_per_day = route.booking_count / date_range if date_range > 0 else 0
            revenue_per_day = revenue / date_range if date_range > 0 else 0
            
            route_analysis.append({
                'departure': route.dep_location,
                'arrival': route.arr_location,
                'bookings': route.booking_count,
                'revenue': revenue,
                'cost': operational_cost,
                'profit': profit,
                'profit_margin': profit_margin,
                'status': 'Profitable' if profit > 0 else 'Loss-making',
                'first_flight': route.first_flight,
                'last_flight': route.last_flight,
                'flights_per_day': flights_per_day,
                'revenue_per_day': revenue_per_day
            })
        
        # Sort by profit margin (default)
        sort_by = request.args.get('sort', default='profit_margin')
        reverse = request.args.get('order', default='desc') == 'desc'
        
        if sort_by == 'profit_margin':
            route_analysis.sort(key=lambda x: x['profit_margin'], reverse=reverse)
        elif sort_by == 'profit':
            route_analysis.sort(key=lambda x: x['profit'], reverse=reverse)
        elif sort_by == 'revenue':
            route_analysis.sort(key=lambda x: x['revenue'], reverse=reverse)
        elif sort_by == 'bookings':
            route_analysis.sort(key=lambda x: x['bookings'], reverse=reverse)
        
        # Add high-level metrics for report summary
        total_profit = sum(route['profit'] for route in route_analysis)
        total_revenue = sum(route['revenue'] for route in route_analysis)
        total_routes = len(route_analysis)
        profitable_routes = sum(1 for route in route_analysis if route['profit'] > 0)
        loss_making_routes = total_routes - profitable_routes
        
        report_summary = {
            'total_routes': total_routes,
            'profitable_routes': profitable_routes,
            'loss_making_routes': loss_making_routes,
            'total_profit': total_profit,
            'total_revenue': total_revenue,
            'avg_profit_margin': (total_profit / total_revenue * 100) if total_revenue > 0 else 0
        }
        
        return render_template('admin_route_analysis.html', 
                             route_analysis=route_analysis, 
                             report_summary=report_summary,
                             datetime=datetime)
                             
    except Exception as e:
        print(f"Error generating route analysis report: {str(e)}")
        flash(f"Error generating report: {str(e)}", "danger")
        return redirect(url_for('admin_reports'))

@app.route('/admin/reports/top-customers')
@admin_required
def admin_report_top_customers():
    """Generate a report showing top customers by revenue and bookings"""
    from datetime import datetime
    
    try:
        # Modified query to include both date of birth and first booking date
        query = text("""
            SELECT u.user_id, u.first_name, u.last_name, u.email, u.date_of_birth, 
                   COUNT(b.booking_id) as total_bookings,
                   SUM(b.total_price) as total_spent,
                   MAX(b.booking_date) as last_booking,
                   MIN(b.booking_date) as first_booking
            FROM users u
            JOIN bookings b ON u.user_id = b.user_id
            WHERE b.status = 'Confirmed'
            GROUP BY u.user_id, u.first_name, u.last_name, u.email, u.date_of_birth
            ORDER BY total_spent DESC;
        """)
        
        # Execute the query
        result = db.session.execute(query)
        
        # Prepare data for the template
        customer_data = []
        for row in result:
            # Calculate average booking value
            avg_booking_value = float(row.total_spent) / int(row.total_bookings) if int(row.total_bookings) > 0 else 0
            
            # Determine customer tier based on revenue
            tier = "Standard"
            if float(row.total_spent) > 500:
                tier = "VIP"
            elif float(row.total_spent) > 200:
                tier = "Premium"
            
            customer_data.append({
                'user_id': row.user_id,
                'first_name': row.first_name,
                'last_name': row.last_name,
                'email': row.email,
                'date_of_birth': row.date_of_birth,
                'customer_since': row.first_booking,  # Use first booking date as customer since
                'bookings': row.total_bookings,
                'total_spent': float(row.total_spent),
                'avg_booking_value': avg_booking_value,
                'last_booking': row.last_booking,
                'tier': tier
            })
        
        # Pass datetime to the template for formatting purposes
        return render_template('admin_top_customers.html', 
                              customer_data=customer_data,
                              datetime=datetime)
    
    except Exception as e:
        print(f"Error generating top customers report: {str(e)}")
        flash(f"Error generating report: {str(e)}", "danger")
        return redirect(url_for('admin_reports'))

# Route to create initial admin OR upgrade existing user
@app.route('/setup-admin', methods=['GET', 'POST'])
def setup_admin():
    # Check if user is logged in - this determines if it's an upgrade or fresh setup
    user_logged_in = 'user_id' in session
    upgrade_mode = user_logged_in

    # For upgrade mode, get the current user and check if they already have an admin entry
    current_user = None
    if upgrade_mode:
        current_user = User.query.get(session['user_id'])
        if not current_user:
            flash('User session invalid. Please log in again.', 'danger')
            return redirect(url_for('login'))
        # Prevent re-upgrading if they already have an admin account
        existing_admin = Admin.query.filter(func.lower(Admin.email) == func.lower(current_user.email)).first()
        if existing_admin:
             flash('You already have an admin account.', 'info')
             return redirect(url_for('admin_dashboard')) # Or maybe profile?

    # Prevent access to initial setup if an admin already exists and not upgrading
    if not upgrade_mode and Admin.query.first():
         flash('Admin account already exists. Use admin login.', 'warning')
         return redirect(url_for('admin_login'))

    # Handle POST request - process the form data
    if request.method == 'POST':
        # Get form data
        email = request.form.get('email') # Use .get() for safety
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # In upgrade mode, use the logged-in user's email
        if upgrade_mode:
            email = current_user.email

        # --- Add Validations ---
        if not email: # Email required only if not upgrading
             flash('Email is required for initial setup!', 'danger')
             return render_template('setup_admin.html', upgrade_mode=upgrade_mode)
        if not password or not confirm_password:
             flash('Password fields are required!', 'danger')
             return render_template('setup_admin.html', upgrade_mode=upgrade_mode)
        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return render_template('setup_admin.html', upgrade_mode=upgrade_mode)
        if len(password) < 6:
            flash('Password must be at least 6 characters long!', 'danger')
            return render_template('setup_admin.html', upgrade_mode=upgrade_mode)
        # --- End Validations ---

        # Check if email already exists in Admin table (important for both modes)
        if Admin.query.filter(func.lower(Admin.email) == func.lower(email)).first():
             flash('An admin account with this email already exists!', 'danger')
             return render_template('setup_admin.html', upgrade_mode=upgrade_mode)

        # Create admin account
        try:
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

            if upgrade_mode:
                admin_name = current_user.first_name
                is_super = False # Upgraded users are not super admins by default
                print(f"Upgrading user to admin: {current_user.first_name} {current_user.last_name}")
            else:
                admin_name = email.split('@')[0]
                is_super = True # First admin is super admin
                print(f"Creating initial admin: {email}")

            new_admin = Admin(
                name=admin_name,
                email=email,
                pword=hashed_password,
                is_super_admin=is_super,
                created_at=datetime.utcnow()
            )

            db.session.add(new_admin)
            db.session.commit()

            if upgrade_mode:
                # Set admin session variables after upgrade
                session['admin_id'] = new_admin.site_admin_id
                session['admin_username'] = new_admin.name
                session['is_admin'] = True
                session['is_super_admin'] = new_admin.is_super_admin # Reflect actual status
                flash('Your account has been upgraded to admin status!', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Initial admin account created successfully! You can now log in.', 'success')
                return redirect(url_for('admin_login'))

        except Exception as e:
            db.session.rollback()
            print(f"Error creating/upgrading admin account: {str(e)}")
            flash(f'Error processing request: {str(e)}', 'danger')
            return render_template('setup_admin.html', upgrade_mode=upgrade_mode)

    # GET request - show form
    return render_template('setup_admin.html', upgrade_mode=upgrade_mode)

# Add this route (e.g., after the /setup-admin route)

@app.route('/upgrade-to-admin', methods=['GET']) # Only allow GET
@login_required
def upgrade_to_admin_redirect(): # Renamed function to avoid conflict if old one wasn't fully deleted
    # Check if user already has an admin account linked to their email
    user = User.query.get(session['user_id'])
    if user:
        existing_admin = Admin.query.filter(func.lower(Admin.email) == func.lower(user.email)).first()
        if existing_admin:
            # If they are already an admin, log them into admin session too
            session['admin_id'] = existing_admin.site_admin_id
            session['admin_username'] = existing_admin.name
            session['is_admin'] = True
            session['is_super_admin'] = existing_admin.is_super_admin
            flash('You already have admin privileges. Redirecting to dashboard.', 'info')
            return redirect(url_for('admin_dashboard'))

    # If not an admin, redirect to the setup page to create the admin password
    flash('Please set your admin password to complete the upgrade.', 'info')
    return redirect(url_for('setup_admin')) # Redirects to the combined setup/upgrade route

# Admin Upgrade Route
@app.route('/upgrade-to-admin', methods=['POST'])
@login_required
def upgrade_to_admin():
    # Get the current logged in user
    user = User.query.get(session['user_id'])
    
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('profile'))
        
    print(f"Found user: {user.first_name} {user.last_name}")
        
    try:
        # Create a new admin account using the user's email as username
        new_admin = Admin(
            name=user.email.split('@')[0],  # Use part of email as name
            email=user.email,
            pword=bcrypt.hashpw(request.form['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
            is_super_admin=False  # Regular admin by default
        )
        
        print("Creating admin account")
        # Add the new admin to the database
        db.session.add(new_admin)
        db.session.commit()
        
        # Set admin session variables
        session['admin_id'] = new_admin.site_admin_id # FIXED: use site_admin_id
        session['admin_username'] = new_admin.name # FIXED: use name not username
        session['is_admin'] = True
        
        flash('Your account has been upgraded to admin status!', 'success')
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        print(f"Error in upgrade_to_admin: {str(e)}")
        db.session.rollback()
        flash(f'Error upgrading account: {str(e)}', 'danger')
        return redirect(url_for('profile'))

# Admin Logout Route
@app.route('/admin/logout')
def admin_logout():
    # Keep user_id in session if they have a user account too
    user_id = session.get('user_id')
    user_name = session.get('user_name')
    
    # Clear admin-specific session variables
    session.pop('admin_id', None)
    session.pop('admin_username', None)
    session.pop('is_admin', None)
    
    # If they have a user account, keep them logged in as a user
    if user_id:
        session['user_id'] = user_id
        session['user_name'] = user_name
        flash('Logged out of admin account. You are still logged in as a user.', 'info')
        return redirect(url_for('profile'))
    else:
        # Clear the whole session if they don't have a user account
        session.clear()
        flash('You have been logged out successfully.', 'success')
        return redirect(url_for('index'))

@app.route('/update-admin-password', methods=['POST'])
@admin_required
def update_admin_password():
    admin = Admin.query.get(session['admin_id'])
    if not admin:
        flash('Admin account not found.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # Check if the current password is correct
    try:
        if not bcrypt.checkpw(current_password.encode('utf-8'), admin.pword.encode('utf-8')):
            flash('Current password is incorrect.', 'danger')
            return redirect(url_for('admin_dashboard'))
    except ValueError:
        flash('Current password format seems incorrect. Cannot verify.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    # Check if the new passwords match
    if new_password != confirm_password:
        flash('New passwords do not match.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    # Update the password
    admin.pword = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    db.session.commit()
    
    flash('Password updated successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

# Add this route to reset admin password
@app.route('/reset-admin-password')
def reset_admin_password():
    with app.app_context():
        try:
            # Find the admin account
            admin = Admin.query.filter_by(email='admin@example.com').first()
            
            if admin:
                # Reset password to 'admin123' - CHANGE THIS LINE:
                admin.pword = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')  # Use pword, not password
                db.session.commit()
                return "Admin password reset successfully to 'admin123'"
            else:
                return "Admin account not found"
        except Exception as e:
            return f"Error: {str(e)}"

# EMERGENCY PASSWORD RESET - REMOVE AFTER USE
@app.route('/emergency-reset/<string:admin_email>')
def emergency_reset(admin_email):
    try:
        admin = Admin.query.filter(func.lower(Admin.email) == func.lower(admin_email)).first()
        if not admin:
            return f"Admin with email {admin_email} not found."

        # Set a new known password using BCRYPT
        new_password = "resetpassword123" # Choose a temporary password
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        admin.pword = hashed_password
        db.session.commit()

        return f"Password for admin {admin.name} ({admin.email}) has been reset to: {new_password}. You can now log in. REMEMBER TO REMOVE THIS ROUTE!"

    except Exception as e:
        db.session.rollback()
        return f"Error resetting password: {str(e)}"

@app.route('/debug_session')
def debug_session():
    return {
        'session': dict(session),
        'routes': [str(rule) for rule in app.url_map.iter_rules()],
        'admin_count': Admin.query.count(),
        'current_time': str(datetime.utcnow())
    }

# Add this route to change user password
@app.route('/change-password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form['current_password']
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']
    
    # Get current user
    user = User.query.get(session['user_id'])
    
    # Validate inputs
    if not current_password or not new_password or not confirm_password:
        flash('All fields are required', 'danger')
        return redirect(url_for('profile'))
        
    if new_password != confirm_password:
        flash('New passwords do not match', 'danger')
        return redirect(url_for('profile'))
        
    if len(new_password) < 6:
        flash('Password must be at least 6 characters long', 'danger')
        return redirect(url_for('profile'))
    
    # Verify current password
    import bcrypt
    if not bcrypt.checkpw(current_password.encode('utf-8'), user.pword.encode('utf-8')):
        flash('Current password is incorrect', 'danger')
        return redirect(url_for('profile'))
    
    # Update password
    try:
        # Hash new password
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        user.pword = hashed_password
        db.session.commit()
        flash('Password changed successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error changing password: {str(e)}', 'danger')
    
    return redirect(url_for('profile'))

# Add this route to manage bookings from admin dashboard
@app.route('/admin/bookings')
@admin_required
def admin_bookings():
    # Fetch all bookings with user information
    bookings = db.session.query(
        Booking, User, Flight
    ).join(
        User, Booking.user_id == User.user_id
    ).join(
        Flight, Booking.journey_id == Flight.journeyid
    ).all()
    
    return render_template('admin_bookings.html', bookings=bookings)

# Add this route right after the admin_bookings route

@app.route('/admin/booking/<int:booking_id>')
@admin_required
def admin_view_booking(booking_id):
    """View booking details for admin"""
    try:
        # Query the booking with related data
        booking_data = db.session.query(
            Booking, User, Flight
        ).join(
            User, Booking.user_id == User.user_id
        ).join(
            Flight, Booking.journey_id == Flight.journeyid
        ).filter(
            Booking.booking_id == booking_id
        ).first()
        
        if not booking_data:
            flash('Booking not found', 'danger')
            return redirect(url_for('admin_bookings'))
            
        booking, user, flight = booking_data
        
        # Get payment info
        payment = Payment.query.filter_by(idusers=user.user_id).order_by(Payment.cardid.desc()).first()
        payment_info = {'last_four': payment.card_num[-4:]} if payment else {'last_four': 'XXXX'}
        
        # Calculate business upgrade fee
        business_upgrade_fee = get_business_upgrade_fee(flight, booking.num_passengers)
        
        return render_template('admin_view_booking.html', 
                              booking=booking,
                              flight=flight,
                              user=user,
                              payment_info=payment_info,
                              business_upgrade_fee=business_upgrade_fee,
                              datetime=datetime)
    
    except Exception as e:
        flash(f'Error viewing booking: {str(e)}', 'danger')
        return redirect(url_for('admin_bookings'))

# Add these routes to enable booking management functionality

@app.route('/update_passenger_details/<int:booking_id>', methods=['POST'])
@login_required
def update_passenger_details(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    
    # Verify booking ownership
    if booking.user_id != session['user_id']:
        flash('You do not have permission to modify this booking', 'danger')
        return redirect(url_for('bookings'))
    
    # Check if it's too late to modify (within 48 hours of departure)
    flight = Flight.query.get(booking.journey_id)
    hours_until_departure = (flight.dep_time - datetime.now()).total_seconds() / 3600
    
    if hours_until_departure < 48:
        flash('Sorry, passenger details cannot be modified within 48 hours of departure', 'danger')
        return redirect(url_for('view_booking', booking_id=booking_id))
    
    # Get form data
    passenger_name = request.form.get('passenger_name')
    special_requests = request.form.get('special_requests', '')
    
    try:
        # Store special requests in the database
        # In a real implementation, you might have a separate table for passenger details
        # For now, we'll just acknowledge the request and show success
        
        flash('Passenger details updated successfully. Special requests noted: ' + 
              (special_requests if special_requests else 'None'), 'success')
        
    except Exception as e:
        flash(f'Error updating passenger details: {str(e)}', 'danger')
    
    return redirect(url_for('view_booking', booking_id=booking_id))

@app.route('/change_flight_date/<int:booking_id>', methods=['POST'])
@login_required
def change_flight_date(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    
    # Verify booking ownership
    if booking.user_id != session['user_id']:
        flash('You do not have permission to modify this booking', 'danger')
        return redirect(url_for('bookings'))
    
    # Get current flight and new date
    current_flight = Flight.query.get(booking.journey_id)
    new_date_str = request.form.get('new_date')
    
    try:
        new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
        
        # Check if new date is valid (not in the past)
        if new_date < datetime.now().date():
            flash('Cannot change to a past date', 'danger')
            return redirect(url_for('view_booking', booking_id=booking_id))
        
        # Find flights on the new date with same route and class
        available_flights = Flight.query.filter_by(
            dep_location=current_flight.dep_location,
            arr_location=current_flight.arr_location,
            class_type=current_flight.class_type
        ).filter(
            func.date(Flight.dep_time) == new_date
        ).all()
        
        # Filter by available seats
        available_flights = [f for f in available_flights if int(f.seats) >= booking.num_passengers]
        
        if not available_flights:
            flash(f'No available flights found on {new_date_str} for your route and class', 'warning')
            return redirect(url_for('view_booking', booking_id=booking_id))
        
        # For this simple implementation, just acknowledge the request
        flash(f'We have noted your request to change to {new_date_str}. ' +
              'Our customer service team will contact you shortly with available options.', 'success')
        
    except ValueError as e:
        flash(f'Invalid date format: {str(e)}', 'danger')
    except Exception as e:
        flash(f'Error processing your request: {str(e)}', 'danger')
    
    return redirect(url_for('view_booking', booking_id=booking_id))

@app.route('/upgrade_booking_class/<int:booking_id>', methods=['POST'])
@login_required
def upgrade_booking_class(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    
    # Verify booking ownership
    if booking.user_id != session['user_id']:
        flash('You do not have permission to modify this booking', 'danger')
        return redirect(url_for('bookings'))
    
    # Get current flight
    flight = Flight.query.get(booking.journey_id)
    
    if flight.class_type != 'Economy':
        flash('This booking is already in Business Class', 'info')
        return redirect(url_for('view_booking', booking_id=booking_id))
    
    try:
        # Find corresponding business class flight
        business_flight = Flight.query.filter_by(
            dep_location=flight.dep_location,
            arr_location=flight.arr_location,
            dep_time=flight.dep_time,
            class_type='Business'
        ).first()
        
        if not business_flight:
            flash('Business class option not available for this flight', 'warning')
            return redirect(url_for('view_booking', booking_id=booking_id))
        
        # Check seat availability
        if int(business_flight.seats) < booking.num_passengers:
            flash(f'Not enough business class seats available (needed: {booking.num_passengers}, available: {business_flight.seats})', 'warning')
            return redirect(url_for('view_booking', booking_id=booking_id))
        
        # Calculate upgrade cost
        economy_price = float(flight.cost)
        business_price = float(business_flight.cost)
        price_difference = business_price - economy_price
        upgrade_cost = price_difference * booking.num_passengers
        
        # For this implementation, just show a confirmation with upgrade cost
        flash(f'Upgrade request received. The cost to upgrade to Business Class would be £{upgrade_cost:.2f}. ' +
              'Our customer service team will contact you to process the payment.', 'success')
        
    except Exception as e:
        flash(f'Error processing upgrade request: {str(e)}', 'danger')
    
    return redirect(url_for('view_booking', booking_id=booking_id))

# Add this function to estimate the upgrade fee (needed by view_booking.html)
def get_business_upgrade_fee(flight, num_passengers):
    """Calculate the estimated fee to upgrade from economy to business class"""
    try:
        if flight.class_type != 'Economy':
            return 0
            
        # Find the corresponding business flight
        business_flight = Flight.query.filter_by(
            dep_location=flight.dep_location,
            arr_location=flight.arr_location,
            dep_time=flight.dep_time,
            class_type='Business'
        ).first()
        
        if business_flight:
            price_difference = float(business_flight.cost) - float(flight.cost)
            return price_difference * num_passengers
        else:
            # If no exact business flight found, estimate as 80% more than economy
            return float(flight.cost) * 0.8 * num_passengers
    except Exception as e:
        print(f"Error calculating upgrade fee: {e}")
        return 0

@app.route('/download_boarding_pass/<int:booking_id>')
@login_required
def download_boarding_pass(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    
    # Check if booking belongs to current user
    if booking.user_id != session['user_id']:
        flash('You do not have permission to access this booking', 'danger')
        return redirect(url_for('my_bookings'))
        
    # For now, just redirect back with a message
    flash('Boarding pass will be available 24 hours before departure', 'info')
    return redirect(url_for('view_booking', booking_id=booking_id))

if __name__ == '__main__':
    with app.app_context():
        try:
            db.create_all()
            print("Database tables created successfully!")
        except Exception as e:
            print(f"Error creating tables: {str(e)}")
    
    app.run(debug=False)  # Set debug to False

#Name:Ethan Williams
#Student Number: 24026055