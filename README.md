
# Choir Backend

A comprehensive choir management platform built with Django REST Framework. Designed to streamline choir operations including member management, attendance tracking, subscriptions, and financial records.

## 🎯 Project Overview

ChoirBackend is a multi-tenant SaaS platform that allows multiple choir organizations to manage their operations independently. Each organization has isolated data with role-based access control.

### Key Features

- **Multi-tenancy**: Support for multiple independent organizations
- **Member Management**: Comprehensive member profiles and directory
- **Subscription System**: Yearly subscription periods with flexible membership types
- **Attendance Tracking**: Session-based attendance with historical records
- **Financial Management**: Income/expense tracking with subscription payments
- **Role-Based Access Control**: Granular permissions for different user roles
- **RESTful API**: Clean, documented API endpoints

## 🏗️ Architecture

- **Framework**: Django 5.0+ with Django REST Framework
- **Database**: PostgreSQL (Supabase)
- **Authentication**: JWT (JSON Web Tokens)
- **API Documentation**: DRF Spectacular (OpenAPI/Swagger)
### Project Structure

```
vocalessence_backend/
├── apps/
│   ├── core/                    # Base models (Organization, abstracts)
│   ├── authentication/          # User authentication & authorization
│   ├── members/                 # Member management
│   ├── subscriptions/           # Subscription system
│   ├── attendance/              # Attendance tracking
│   ├── finance/                 # Financial records
│   └── reports/                 # Analytics & reporting
├── config/
│   ├── settings/                # Environment-specific settings
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   └── urls.py                  # Main URL configuration
├── docs/                        # Documentation
├── requirements/                # Python dependencies
│   ├── base.txt
│   ├── development.txt
│   └── production.txt
└── manage.py
```

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- PostgreSQL (or use SQLite for local dev)
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/vocalessence_backend.git
   cd vocalessence_backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   
   # Activate virtual environment
   # On Windows:
   venv\Scripts\activate
   
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements/development.txt
   ```

4. **Environment configuration**
   ```bash
   # Copy environment template
   cp .env.example .env
   
   # Edit .env with your settings
   # Minimum required:
   # - SECRET_KEY (generate using: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
   # - DATABASE_URL (or leave empty to use SQLite)
   ```

5. **Run migrations**
   ```bash
   python manage.py migrate
   ```

6. **Create initial data**
   ```bash
   # This creates a default organization and admin user
   python manage.py setup_initial_data
   
   # Default credentials:
   # Username: admin
   # Password: admin123
   # ⚠️ Change this immediately after first login!
   ```

7. **Run development server**
   ```bash
   python manage.py runserver
   ```

   The API will be available at: http://localhost:8000/

### Initial Setup

After running the server, you can:

- **Admin Interface**: http://localhost:8000/admin/
- **API Documentation**: http://localhost:8000/api/docs/
- **API Root**: http://localhost:8000/api/v1/

## 🔐 Authentication

The API uses JWT (JSON Web Tokens) for authentication.

### Getting a Token

```bash
POST /api/v1/auth/login/
Content-Type: application/json

{
  "username": "admin",
  "password": "admin123"
}
```

**Response:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": "...",
    "username": "admin",
    "email": "admin@vocalessence.com",
    "role": "super_admin",
    "organization_name": "VocalEssence Chorale"
  }
}
```

### Using the Token

Include the access token in the Authorization header:

```bash
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
```

### Token Refresh

```bash
POST /api/v1/auth/refresh/
Content-Type: application/json

{
  "refresh": "your_refresh_token"
}
```

## 📚 API Documentation

### Interactive Documentation

- **Swagger UI**: http://localhost:8000/api/docs/
- **ReDoc**: http://localhost:8000/api/redoc/