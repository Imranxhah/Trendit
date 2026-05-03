# Trendit Backend

A Django REST Framework backend for the Trendit social media application.  
Media files (images & videos) are stored on **Cloudinary** and automatically deleted after **7 days** via a PythonAnywhere scheduled task.

## Tech Stack

- **Framework**: Django 6.0 + Django REST Framework
- **Auth**: JWT (SimpleJWT)
- **Admin**: Unfold (modern Django admin)
- **Database**: SQLite
- **Media Storage**: Cloudinary (free tier — 25GB storage / 25GB bandwidth per month)

---

## 🚀 Deploy on PythonAnywhere (Step-by-Step)

### 1. Clone the Repository

In your PythonAnywhere **Bash console**:

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

### 4. Get Your Cloudinary Credentials

1. Go to [cloudinary.com](https://cloudinary.com) → **Sign Up Free**
2. After logging in, open the **Dashboard**
3. Copy your **Cloud name**, **API Key**, and **API Secret**

### 5. Create Your `.env` File

```bash
cp .env.example .env
nano .env
```

Fill in your values:

```env
SECRET_KEY=your-super-secret-key-here
DEBUG=False
ALLOWED_HOSTS=skorpion.pythonanywhere.com

CORS_ALLOWED_ORIGINS=http://localhost:3000
CORS_ALLOW_ALL_ORIGINS=False

CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

To generate a secure `SECRET_KEY`:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 6. Run Migrations & Collect Static Files

```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

### 7. Create a Superuser (Optional)

```bash
python manage.py createsuperuser
```

### 8. Configure the Web App on PythonAnywhere

1. Go to **Web** tab → **Add a new web app**
2. Choose **Manual configuration** → Select **Python 3.11**
3. Set the **Source code** directory: `/home/skorpion/Trendit`
4. Set the **Working directory**: `/home/skorpion/Trendit`
5. Set the **Virtualenv** path: `/home/skorpion/Trendit/venv`

### 9. Configure the WSGI File

Click the WSGI configuration file link in the Web tab and replace its entire contents with:

```python
import sys
import os

path = '/home/skorpion/Trendit'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'trendit_backend.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

### 10. Configure Static Files

In the **Web** tab → **Static files** section, add:

| URL        | Directory                                          |
|------------|----------------------------------------------------|
| `/static/` | `/home/skorpion/Trendit/staticfiles/`          |

> Media files are served directly from Cloudinary — no local `/media/` entry needed.

### 11. Set Up Automatic Weekly Media Deletion

PythonAnywhere's **Scheduled Tasks** run your management command daily to delete Cloudinary files older than 7 days.

1. Go to the **Tasks** tab on PythonAnywhere
2. Click **Add a new scheduled task**
3. Set it to run **Daily** (e.g., at `02:00`)
4. Enter this command:

```bash
/home/skorpion/Trendit/venv/bin/python /home/skorpion/Trendit/manage.py delete_expired_media
```

That's it! Media files will be automatically deleted from Cloudinary every night, 7 days after they were posted.

### 12. Reload the Web App

Click **Reload** on the Web tab. Your API is live at:  
`https://skorpion.pythonanywhere.com/`

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

## How Media Deletion Works

1. User uploads a post/sub-post → file goes to **Cloudinary** automatically
2. Every night, the scheduled task runs `python manage.py delete_expired_media`
3. The command finds all posts where `created_at < now - 7 days` and `is_media_deleted=False`
4. It calls **Cloudinary's API** to delete the file from the cloud
5. The DB record's `media_file` is cleared and `is_media_deleted = True` is set
6. The post/sub-post record itself is **kept** in the database

---

## Local Development

```bash
git clone https://github.com/Imranxhah/Trendit.git
cd Trendit

python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate         # Windows

pip install -r requirements.txt

cp .env.example .env
# Edit .env: set DEBUG=True, SECRET_KEY, and your Cloudinary credentials

python manage.py migrate
python manage.py runserver
```

The API will be available at `http://127.0.0.1:8000/`
