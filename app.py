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
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///salon.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Database Models
class Shop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    owner_username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    appointments = db.relationship('Appointment', backref='shop', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)
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
def generate_qr_code(shop_id):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    booking_url = f"{request.host_url}book/{shop_id}"
    qr.add_data(booking_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    return img_io

def get_available_time_slots(shop_id, date):
    # This is a simplified version. In a real application, you'd want to:
    # 1. Get shop's working hours
    # 2. Check existing appointments
    # 3. Return available slots
    slots = []
    start_time = datetime.strptime('09:00', '%H:%M')
    end_time = datetime.strptime('17:00', '%H:%M')
    interval = timedelta(minutes=30)

    current_time = start_time
    while current_time < end_time:
        time_str = current_time.strftime('%H:%M')
        is_booked = Appointment.query.filter_by(
            shop_id=shop_id,
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

@app.route('/book/<int:shop_id>', methods=['GET', 'POST'])
def book_appointment(shop_id):
    shop = Shop.query.get_or_404(shop_id)
    date = request.args.get('date', datetime.now().date())
    
    if request.method == 'POST':
        time_slot = request.form.get('time_slot')
        customer_name = request.form.get('name')
        phone_number = request.form.get('phone')
        
        # Check if slot is still available
        existing_appointment = Appointment.query.filter_by(
            shop_id=shop_id,
            date=date,
            time_slot=time_slot
        ).first()
        
        if existing_appointment:
            flash('This time slot has already been booked. Please choose another.', 'danger')
            return redirect(url_for('book_appointment', shop_id=shop_id))
        
        appointment = Appointment(
            shop_id=shop_id,
            date=date,
            time_slot=time_slot,
            customer_name=customer_name,
            phone_number=phone_number
        )
        
        db.session.add(appointment)
        db.session.commit()
        
        flash('Appointment booked successfully!', 'success')
        return redirect(url_for('book_appointment', shop_id=shop_id))
    
    time_slots = get_available_time_slots(shop_id, date)
    return render_template('booking.html', 
                         shop=shop,
                         time_slots=time_slots,
                         today=datetime.now().date(),
                         max_date=datetime.now().date() + timedelta(days=30))

@app.route('/owner/login', methods=['GET', 'POST'])
def owner_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        shop = Shop.query.filter_by(owner_username=username).first()
        if shop and shop.check_password(password):
            login_user(shop)
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
            shop_id=current_user.id,
            date=today
        ).order_by(Appointment.time_slot).all()
    elif filter_type == 'week':
        week_end = today + timedelta(days=7)
        appointments = Appointment.query.filter(
            Appointment.shop_id == current_user.id,
            Appointment.date >= today,
            Appointment.date <= week_end
        ).order_by(Appointment.date, Appointment.time_slot).all()
    else:  # month
        month_end = today + timedelta(days=30)
        appointments = Appointment.query.filter(
            Appointment.shop_id == current_user.id,
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
    shops = Shop.query.all()
    total_appointments = Appointment.query.count()
    active_bookings = Appointment.query.filter_by(status='pending').count()
    
    return render_template('admin/dashboard.html',
                         shops=shops,
                         total_shops=len(shops),
                         total_appointments=total_appointments,
                         active_bookings=active_bookings)

@app.route('/admin/shop', methods=['POST'])
@login_required
def create_shop():
    data = request.get_json()
    
    shop = Shop(
        name=data['name'],
        address=data['address'],
        owner_username=data['owner_username']
    )
    shop.set_password(data['owner_password'])
    
    db.session.add(shop)
    db.session.commit()
    
    return jsonify({'success': True, 'shop_id': shop.id})

@app.route('/admin/shop/<int:shop_id>', methods=['DELETE'])
@login_required
def delete_shop(shop_id):
    shop = Shop.query.get_or_404(shop_id)
    
    # Delete all appointments for this shop
    Appointment.query.filter_by(shop_id=shop_id).delete()
    
    db.session.delete(shop)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/shop/<int:shop_id>/qr')
@login_required
def get_shop_qr(shop_id):
    img_io = generate_qr_code(shop_id)
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