# WeDesignz API

A comprehensive Django REST API for the WeDesignz platform - a design marketplace with subscription plans, custom orders, and advanced features.

## 🚀 Features

### Authentication & User Management
- JWT-based authentication
- Email and mobile verification via OTP
- Password reset functionality
- User profile management
- Address management

### Design Catalog
- Dynamic home feed with designs and bundles
- Advanced search and filtering
- Category and tag management
- Trending and recently added designs
- Infinite scroll pagination

### Orders & Cart Management
- Shopping cart functionality
- Wishlist management
- Order processing
- Download management
- Free purchases for subscribers

### Subscription Plans
- Monthly and annual plans
- Auto-renewal functionality
- Subscription management
- Usage tracking

### Payment Integration
- Razorpay payment gateway
- Wallet system
- Transaction management
- Refund processing

### Custom Orders
- Configurable delivery promise (default: 1 hour)
- Admin notifications
- Timer system
- Custom design requests

### Background Tasks & Automation
- Celery for background processing
- Scheduled tasks (cron jobs)
- Email automation
- Data cleanup
- Backup management

## 🛠️ Technology Stack

- **Backend**: Django 5.2.7, Django REST Framework
- **Database**: PostgreSQL
- **Authentication**: JWT (djangorestframework-simplejwt)
- **Background Tasks**: Celery, Celery Beat
- **Message Broker**: Redis
- **Payment**: Razorpay
- **Documentation**: drf-yasg (Swagger/OpenAPI)
- **Admin**: Django Admin with Jazzmin theme

## 📋 Prerequisites

- Python 3.11+
- PostgreSQL
- Redis
- pip

## 🔧 Installation

### 1. Clone the Repository
```bash
git clone <repository-url>
cd API
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Environment Configuration
Create a `.env` file in the root directory:
```env
SECRET_KEY=your-secret-key
DEBUG=True
DATABASE_URL=postgresql://user:password@localhost:5432/wedesignz
CELERY_BROKER_URL=redis://localhost:6379/0
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
RAZORPAY_KEY_ID=your-razorpay-key-id
RAZORPAY_KEY_SECRET=your-razorpay-key-secret
```

### 5. Database Setup
```bash
python manage.py migrate
python manage.py createsuperuser
```

### 6. Start Services
```bash
# Start Redis
redis-server

# Start PostgreSQL
sudo systemctl start postgresql

# Start Django server
python manage.py runserver

# Start Celery worker (in another terminal)
celery -A API worker --loglevel=info

# Start Celery beat (in another terminal)
celery -A API beat --loglevel=info

# Start Flower monitoring (in another terminal)
celery -A API flower --port=5555
```

## 🚀 Quick Start

### Manual Service Startup
```bash
# Start Redis
redis-server

# Start PostgreSQL
sudo systemctl start postgresql

# Start Django server
python manage.py runserver

# Start Celery worker (in another terminal)
celery -A API worker --loglevel=info

# Start Celery beat (in another terminal)
celery -A API beat --loglevel=info

# Start Flower monitoring (in another terminal)
celery -A API flower --port=5555
```

## 📚 API Documentation

### Base URL
```
http://localhost:8000/api/
```

### Authentication Endpoints
- `POST /api/auth/signup/` - User registration
- `POST /api/auth/login/` - User login
- `POST /api/auth/logout/` - User logout
- `POST /api/auth/verify-email/` - Email verification
- `POST /api/auth/password-reset-request/` - Password reset request
- `POST /api/auth/password-reset-confirm/` - Password reset confirmation

### Catalog Endpoints
- `GET /api/catalog/landing-page/` - Landing page data
- `GET /api/catalog/home-feed/` - Home feed with designs and bundles
- `GET /api/catalog/search-filter/` - Search and filter designs
- `GET /api/catalog/products/<id>/` - Product details

### Order Endpoints
- `GET /api/orders/cart/` - Get cart items
- `POST /api/orders/cart/add/` - Add to cart
- `POST /api/orders/purchase/` - Purchase cart items
- `GET /api/orders/downloads/` - User downloads

### Plan Endpoints
- `GET /api/plans/plans/` - Get all plans
- `POST /api/plans/subscription/subscribe/` - Subscribe to plan
- `GET /api/plans/subscription/` - Get user subscription

### Payment Endpoints
- `POST /api/razorpay/create-order/` - Create payment order
- `POST /api/razorpay/capture-payment/` - Capture payment
- `GET /api/razorpay/payment/<id>/status/` - Payment status

## 🔍 API Documentation

- **Swagger UI**: http://localhost:8000/swagger/
- **ReDoc**: http://localhost:8000/redoc/
- **Admin Panel**: http://localhost:8000/admin/
- **Flower Monitoring**: http://localhost:5555

## 📅 Scheduled Tasks

### Automatic Tasks (Celery Beat)
- **OTP Cleanup** - Every 5 minutes
- **Custom Order Timeouts** - Every 5 minutes
- **Subscription Status Updates** - Every hour
- **Auto-mandate Notifications** - Every hour
- **Daily Backup** - Every day at 2 AM
- **Coupon Expiration** - Every day at 2 AM
- **Inactive Accounts Cleanup** - Every day at 2 AM
- **Weekly Backup** - Every Sunday at 3 AM
- **Subscription Expiry Reminders** - Every Sunday at 3 AM
- **Promotional Emails** - Every 3 days at 10 AM

## 🧪 Testing

### Run All Tests
```bash
# Run all tests
python manage.py test

# Run tests for specific app
python manage.py test Authentication

# Run tests with coverage
pip install coverage
coverage run --source='.' manage.py test
coverage report
coverage html
```

### Test Commands
```bash
# Run tests with verbose output
python manage.py test --verbosity=2

# Run tests in parallel
python manage.py test --parallel

# Run tests with keepdb (faster for repeated runs)
python manage.py test --keepdb

# Run specific test class
python manage.py test Authentication.tests.UserRegistrationTestCase

# Run specific test method
python manage.py test Authentication.tests.UserRegistrationTestCase.test_user_registration_success
```

### Test Coverage
```bash
# Install coverage
pip install coverage

# Run tests with coverage
coverage run --source='.' manage.py test

# Generate coverage report
coverage report

# Generate HTML coverage report
coverage html

# Open coverage report in browser
open htmlcov/index.html
```

## 🎛️ Management Commands

### Database Operations
```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Load initial data
python manage.py loaddata initial_data.json
```

### Service Management
```bash
# Start Redis
redis-server

# Start PostgreSQL
sudo systemctl start postgresql

# Start Django server
python manage.py runserver

# Start Celery worker
celery -A API worker --loglevel=info

# Start Celery beat
celery -A API beat --loglevel=info

# Start Flower monitoring
celery -A API flower --port=5555
```

## 📊 Monitoring

### Django Admin
- Manage periodic tasks
- View task results
- Execute manual tasks
- Monitor system health

### Flower Dashboard
- Real-time task monitoring
- Worker status
- Task history
- Queue management

## 🔧 Configuration

### Celery Settings
```python
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'django-db'
CELERY_TIMEZONE = 'Asia/Kolkata'
```

### Email Settings
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
```

## 🚀 Production Deployment

### 1. Environment Setup
```bash
export DEBUG=False
export CELERY_BROKER_URL=redis://your-redis-server:6379/0
export DATABASE_URL=postgresql://user:password@your-db-server:5432/wedesignz
```

### 2. Database Migration
```bash
python manage.py migrate
python manage.py collectstatic
```

### 3. Start Services
```bash
# Using supervisor or systemd
celery -A API worker --loglevel=info --daemon
celery -A API beat --loglevel=info --daemon
gunicorn API.wsgi:application --bind 0.0.0.0:8000
```

## 🔐 Security

- JWT token authentication
- CORS configuration
- Input validation
- SQL injection protection
- XSS protection
- CSRF protection

## 📈 Performance

- Database query optimization
- Caching strategies
- Background task processing
- Queue management
- Worker scaling

## 🐛 Troubleshooting

### Common Issues

1. **Redis Connection Error**
   ```bash
   redis-cli ping
   ```

2. **Database Connection Error**
   ```bash
   python manage.py dbshell
   ```

3. **Celery Worker Issues**
   ```bash
   celery -A API inspect active
   ```

## 📝 License

This project is licensed under the MIT License.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📞 Support

For support and questions:
- Check the documentation
- Review the troubleshooting section
- Contact the development team

## 🎯 Roadmap

- [ ] Mobile app integration
- [ ] Advanced analytics
- [ ] Machine learning recommendations
- [ ] Multi-language support
- [ ] Advanced payment options
- [ ] Real-time notifications
- [ ] Advanced search algorithms
- [ ] Social features
- [ ] API rate limiting
- [ ] Advanced caching