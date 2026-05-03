# Trendit Backend

A Django REST Framework backend for the Trendit social media application.

## Tech Stack

- **Framework**: Django 6.0 + Django REST Framework
- **Auth**: JWT (SimpleJWT)
- **Admin**: Unfold (modern Django admin)
- **Database**: SQLite (easy to switch to PostgreSQL/MySQL)
- **Other**: CORS headers, Phone number field

---

## 🚀 Deploy on PythonAnywhere (Step-by-Step)

### 1. Clone the Repository

In your PythonAnywhere **Bash console**, run:

```bash
git clone https://github.com/Imranxhah/Trendit.git
cd Trendit
```

### 2. Create a Virtual Environment

```bash
python3.11 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Create Your `.env` File

```bash
cp .env.example .env
nano .env
```

Edit the file with your actual values:

```
SECRET_KEY=your-super-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourusername.pythonanywhere.com
CORS_ALLOWED_ORIGINS=http://localhost:3000
CORS_ALLOW_ALL_ORIGINS=False
```

To generate a secure `SECRET_KEY`:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 5. Run Migrations

```bash
python manage.py migrate
```

### 6. Collect Static Files

```bash
python manage.py collectstatic --noinput
```

### 7. Create a Superuser (Optional)

```bash
python manage.py createsuperuser
```

### 8. Configure the Web App on PythonAnywhere

1. Go to **Web** tab → **Add a new web app**
2. Choose **Manual configuration** → Select **Python 3.11**
3. Set the **Source code** directory:  
   `/home/yourusername/Trendit`
4. Set the **Working directory**:  
   `/home/yourusername/Trendit`
5. Set the **Virtualenv** path:  
   `/home/yourusername/Trendit/venv`

### 9. Configure the WSGI File

Click on the WSGI configuration file link in the Web tab and replace its contents with:

```python
import sys
import os

# Add the project to the path
path = '/home/yourusername/Trendit'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'trendit_backend.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

### 10. Configure Static Files

In the **Web** tab → **Static files** section, add:

| URL       | Directory                                        |
|-----------|--------------------------------------------------|
| `/static/` | `/home/yourusername/Trendit/staticfiles/`       |
| `/media/`  | `/home/yourusername/Trendit/media/`             |

### 11. Reload the Web App

Click the **Reload** button on the Web tab. Your API will be live at:  
`https://yourusername.pythonanywhere.com/`

---

## API Endpoints

See [API_DOCUMENTATION.md](API_DOCUMENTATION.md) for full endpoint reference.

| App      | Base URL         |
|----------|------------------|
| Users    | `/api/users/`    |
| Content  | `/api/content/`  |
| Social   | `/api/social/`   |
| Core     | `/api/core/`     |
| Admin    | `/admin/`        |

---

## Local Development

```bash
# Clone and enter the directory
git clone https://github.com/Imranxhah/Trendit.git
cd Trendit

# Create and activate venv
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env: set DEBUG=True and SECRET_KEY

# Run migrations and start server
python manage.py migrate
python manage.py runserver
```

The API will be available at `http://127.0.0.1:8000/`
