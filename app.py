from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import qrcode
import io
from datetime import datetime, timedelta
import os
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///appointment.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Database Models
class Business(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    owner_username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    appointments = db.relationship('Appointment', backref='business', lazy=True)
    working_hours = db.Column(db.String(200), default='09:00-17:00')
    slot_duration = db.Column(db.Integer, default=30)  # in minutes

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('business.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time_slot = db.Column(db.String(50), nullable=False)
    customer_name = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='pending')

class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return Admin.query.get(int(user_id))

# Helper Functions
def generate_qr_code(business_id):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    booking_url = f"{request.host_url}book/{business_id}"
    qr.add_data(booking_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    return img_io

def get_available_time_slots(business_id, date):
    business = Business.query.get(business_id)
    if not business:
        return []
    
    # Parse working hours
    start_time_str, end_time_str = business.working_hours.split('-')
    start_time = datetime.strptime(start_time_str, '%H:%M')
    end_time = datetime.strptime(end_time_str, '%H:%M')
    interval = timedelta(minutes=business.slot_duration)

    slots = []
    current_time = start_time
    while current_time < end_time:
        time_str = current_time.strftime('%H:%M')
        is_booked = Appointment.query.filter_by(
            business_id=business_id,
            date=date,
            time_slot=time_str
        ).first() is not None

        slots.append({
            'time': time_str,
            'is_booked': is_booked
        })
        current_time += interval

    return slots

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/book/<int:business_id>', methods=['GET', 'POST'])
def book_appointment(business_id):
    business = Business.query.get_or_404(business_id)
    date = request.args.get('date')
    if date:
        date = datetime.strptime(date, '%Y-%m-%d').date()
    else:
        date = datetime.now().date()
    
    if request.method == 'POST':
        time_slot = request.form.get('time_slot')
        customer_name = request.form.get('name')
        phone_number = request.form.get('phone')
        
        # Check if slot is still available
        existing_appointment = Appointment.query.filter_by(
            business_id=business_id,
            date=date,
            time_slot=time_slot
        ).first()
        
        if existing_appointment:
            flash('This time slot has already been booked. Please choose another.', 'danger')
            return redirect(url_for('book_appointment', business_id=business_id))
        
        appointment = Appointment(
            business_id=business_id,
            date=date,
            time_slot=time_slot,
            customer_name=customer_name,
            phone_number=phone_number
        )
        
        db.session.add(appointment)
        db.session.commit()
        
        flash('Appointment booked successfully!', 'success')
        return redirect(url_for('book_appointment', business_id=business_id))
    
    time_slots = get_available_time_slots(business_id, date)
    return render_template('booking.html', 
                         business=business,
                         time_slots=time_slots,
                         selected_date=date,
                         today=datetime.now().date(),
                         max_date=datetime.now().date() + timedelta(days=30))

@app.route('/api/time-slots/<int:business_id>')
def get_time_slots(business_id):
    date_str = request.args.get('date')
    if not date_str:
        return jsonify({'error': 'Date parameter is required'}), 400
    
    date = datetime.strptime(date_str, '%Y-%m-%d').date()
    time_slots = get_available_time_slots(business_id, date)
    return jsonify(time_slots)

@app.route('/owner/login', methods=['GET', 'POST'])
def owner_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        business = Business.query.filter_by(owner_username=username).first()
        if business and business.check_password(password):
            login_user(business)
            return redirect(url_for('owner_dashboard'))
        
        flash('Invalid username or password', 'danger')
    return render_template('owner/login.html')

@app.route('/owner/dashboard')
@login_required
def owner_dashboard():
    filter_type = request.args.get('filter', 'today')
    today = datetime.now().date()
    
    if filter_type == 'today':
        appointments = Appointment.query.filter_by(
            business_id=current_user.id,
            date=today
        ).order_by(Appointment.time_slot).all()
    elif filter_type == 'week':
        week_end = today + timedelta(days=7)
        appointments = Appointment.query.filter(
            Appointment.business_id == current_user.id,
            Appointment.date >= today,
            Appointment.date <= week_end
        ).order_by(Appointment.date, Appointment.time_slot).all()
    else:  # month
        month_end = today + timedelta(days=30)
        appointments = Appointment.query.filter(
            Appointment.business_id == current_user.id,
            Appointment.date >= today,
            Appointment.date <= month_end
        ).order_by(Appointment.date, Appointment.time_slot).all()
    
    return render_template('owner/dashboard.html', appointments=appointments)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        admin = Admin.query.filter_by(username=username).first()
        if admin and admin.check_password(password):
            login_user(admin)
            return redirect(url_for('admin_dashboard'))
        
        flash('Invalid username or password', 'danger')
    return render_template('admin/login.html')

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    businesses = Business.query.all()
    total_appointments = Appointment.query.count()
    active_bookings = Appointment.query.filter_by(status='pending').count()
    
    return render_template('admin/dashboard.html',
                         businesses=businesses,
                         total_businesses=len(businesses),
                         total_appointments=total_appointments,
                         active_bookings=active_bookings)

@app.route('/admin/business', methods=['POST'])
@login_required
def create_business():
    data = request.get_json()
    
    business = Business(
        name=data['name'],
        address=data['address'],
        owner_username=data['owner_username'],
        working_hours=data.get('working_hours', '09:00-17:00'),
        slot_duration=data.get('slot_duration', 30)
    )
    business.set_password(data['owner_password'])
    
    db.session.add(business)
    db.session.commit()
    
    return jsonify({'success': True, 'business_id': business.id})

@app.route('/admin/business/<int:business_id>', methods=['DELETE'])
@login_required
def delete_business(business_id):
    business = Business.query.get_or_404(business_id)
    
    # Delete all appointments for this business
    Appointment.query.filter_by(business_id=business_id).delete()
    
    db.session.delete(business)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/business/<int:business_id>/qr')
@login_required
def get_business_qr(business_id):
    img_io = generate_qr_code(business_id)
    return send_file(img_io, mimetype='image/png')

@app.route('/appointment/<int:appointment_id>/confirm', methods=['POST'])
@login_required
def confirm_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    appointment.status = 'confirmed'
    db.session.commit()
    return jsonify({'success': True})

@app.route('/appointment/<int:appointment_id>/cancel', methods=['POST'])
@login_required
def cancel_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    appointment.status = 'cancelled'
    db.session.commit()
    return jsonify({'success': True})

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Create default admin if not exists
        if not Admin.query.first():
            admin = Admin(username='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
    
    app.run(debug=True) 