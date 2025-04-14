# Salon Appointment Booking System

A web-based appointment booking system that allows customers to book appointments by scanning shop-specific QR codes. Shop owners can manage their appointments through a dashboard, and system administrators can manage all shops and generate QR codes.

## Features

- Customer booking through QR code scanning
- Shop owner dashboard for appointment management
- Admin panel for shop management
- QR code generation for each shop
- Real-time appointment tracking
- Multi-shop support

## Tech Stack

- Backend: Python (Flask)
- Frontend: HTML/CSS/JS (Bootstrap)
- Database: SQLite (development) / PostgreSQL (production)
- QR Code Generation: Python qrcode library
- Authentication: Flask-Login

## Setup Instructions

1. Clone the repository:
```bash
git clone <repository-url>
cd salon-booking-system
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
# Create a .env file with the following variables
SECRET_KEY=your-secret-key
DATABASE_URL=sqlite:///salon.db
```

5. Initialize the database:
```bash
flask db init
flask db migrate
flask db upgrade
```

6. Run the application:
```bash
flask run
```

## Usage

### Admin Access
1. Access the admin panel at `/admin/login`
2. Default admin credentials:
   - Username: admin
   - Password: admin123 (change this in production)

### Shop Owner Access
1. Shop owners can log in at `/owner/login`
2. Credentials are set by the admin when creating a shop

### Customer Booking
1. Customers scan the shop's QR code
2. They are directed to the booking page
3. Select a date and time slot
4. Enter their details and confirm the booking

## Project Structure

```
salon-booking-system/
├── app.py                  # Main application file
├── requirements.txt        # Project dependencies
├── .env                    # Environment variables
├── instance/              # Database instance
├── static/                # Static files (CSS, JS, images)
│   ├── css/
│   └── js/
└── templates/             # HTML templates
    ├── admin/            # Admin panel templates
    ├── owner/            # Shop owner templates
    └── booking/          # Customer booking templates
```

## Security Considerations

- All passwords are hashed using Werkzeug's security utilities
- Admin and owner routes are protected with login_required
- Input validation on all forms
- Rate limiting on booking endpoints (optional)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 