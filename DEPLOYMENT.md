# PITAYA Deployment Guide

This guide covers deploying PITAYA (Plant Illness Tracking and Automated Yield Analysis System) as an Android APK and hosting the backend in production.

## Table of Contents

1. [APK Creation (Android)](#apk-creation-android)
2. [Backend Production Hosting](#backend-production-hosting)
3. [Frontend Deployment](#frontend-deployment)
4. [Environment Setup](#environment-setup)

---

## APK Creation (Android)

### Prerequisites

- **Node.js** (v18 or higher)
- **npm** or **yarn**
- **Android Studio** (for building APK)
- **Java JDK** (v11 or higher)
- **Android SDK** (API level 33+)

### Step 1: Build the Frontend

```bash
cd frontend
npm install
npm run build
```

This creates the `dist/` folder with production-ready static files.

### Step 2: Sync with Capacitor

```bash
npx cap sync android
```

This copies the built files to the Android project.

### Step 3: Open in Android Studio

```bash
npx cap open android
```

This opens the Android project in Android Studio.

### Step 4: Build APK in Android Studio

1. In Android Studio, go to **Build > Build Bundle(s) / APK(s) > Build APK(s)**
2. Wait for the build to complete
3. The APK will be located at: `android/app/build/outputs/apk/debug/app-debug.apk`

### Step 5: Build Release APK (for distribution)

1. In Android Studio, go to **Build > Generate Signed Bundle / APK**
2. Select **APK** and click **Next**
3. Create or import a keystore file
4. Select **release** build variant
5. The release APK will be in: `android/app/build/outputs/apk/release/app-release.apk`

### Step 6: Install on Device

```bash
adb install android/app/build/outputs/apk/debug/app-debug.apk
```

Or transfer the APK file to your device and install directly.

---

## Backend Production Hosting

### Prerequisites

- **Python** (v3.8 or higher)
- **pip** package manager
- **PostgreSQL** or **MySQL** (recommended for production)
- **Domain name** (optional)

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` with your production values:

```env
FLASK_ENV=production
FLASK_DEBUG=0
SECRET_KEY=your-secret-key-here-change-in-production
HOST=0.0.0.0
PORT=5000
DATABASE_URL=postgresql://user:password@localhost/pitaya_db
DASHBOARD_API_URL=http://localhost:5001
MODEL_PATH=leaf_disease_model.keras
LOG_LEVEL=INFO
CORS_ORIGINS=https://yourdomain.com
```

### Step 3: Database Setup (PostgreSQL Example)

```bash
# Create database
createdb pitaya_db

# Or using psql
psql -U postgres
CREATE DATABASE pitaya_db;
\q
```

### Step 4: Start Production Server

**Linux/Mac:**
```bash
chmod +x start_production.sh
./start_production.sh
```

**Windows:**
```cmd
start_production.bat
```

Or manually with Gunicorn:
```bash
gunicorn app:app --bind 0.0.0.0:5000 --workers 4 --worker-class sync --timeout 120
```

### Step 5: Set Up Reverse Proxy (Nginx Example)

Create `/etc/nginx/sites-available/pitaya`:

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Increase upload size for disease detection images
    client_max_body_size 10M;
}
```

Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/pitaya /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Step 6: Set Up SSL (Let's Encrypt)

```bash
sudo certbot --nginx -d yourdomain.com
```

### Step 7: Set Up Process Manager (Systemd)

Create `/etc/systemd/system/pitaya.service`:

```ini
[Unit]
Description=PITAYA Backend API
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/Activity-AppDev
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/gunicorn app:app --bind 0.0.0.0:5000 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable pitaya
sudo systemctl start pitaya
```

---

## Frontend Deployment

### Option 1: Static Hosting (Vercel, Netlify, AWS S3)

1. Build the frontend:
```bash
cd frontend
npm run build
```

2. Deploy the `dist/` folder to your chosen platform.

**Vercel:**
```bash
npm install -g vercel
vercel --prod
```

**Netlify:**
```bash
npm install -g netlify-cli
netlify deploy --prod --dir=dist
```

### Option 2: Serve with Nginx

Add to your Nginx configuration:

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    # Frontend static files
    location / {
        root /path/to/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # Backend API
    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Disease prediction endpoint
    location /predict {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        client_max_body_size 10M;
    }
}
```

---

## Environment Setup

### Development Environment

**Backend:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

### Production Environment

**Backend:**
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with production values
./start_production.sh
```

**Frontend:**
```bash
cd frontend
npm install
npm run build
# Deploy dist/ folder
```

---

## Cloud Deployment Options

### Backend

1. **Render** - Easy deployment, free tier available
2. **Railway** - Simple deployment with PostgreSQL
3. **Heroku** - Established platform, requires paid dyno
4. **AWS EC2** - Full control, requires more setup
5. **DigitalOcean** - Affordable VPS options

### Frontend

1. **Vercel** - Best for React apps, free tier
2. **Netlify** - Great static hosting, free tier
3. **AWS S3 + CloudFront** - Scalable, pay-as-you-go
4. **GitHub Pages** - Free for public repos

---

## Troubleshooting

### APK Build Issues

- **Gradle sync fails**: Check Android SDK installation
- **Build errors**: Ensure Java JDK 11+ is installed
- **App crashes**: Check `adb logcat` for error logs

### Backend Issues

- **Port already in use**: Change PORT in .env or kill existing process
- **Database connection failed**: Verify DATABASE_URL and database is running
- **Model loading failed**: Ensure model file exists in correct path

### Frontend Issues

- **API calls failing**: Check CORS configuration in backend
- **Build errors**: Clear node_modules and reinstall: `rm -rf node_modules && npm install`
- **Deployment issues**: Check build output in dist/ folder

---

## Security Recommendations

1. **Change SECRET_KEY** in production
2. **Use HTTPS** for all communications
3. **Restrict CORS origins** to your domain only
4. **Use environment variables** for sensitive data
5. **Keep dependencies updated** regularly
6. **Implement rate limiting** for API endpoints
7. **Add authentication** for admin features
8. **Use PostgreSQL/MySQL** instead of SQLite in production
9. **Enable firewall** rules to restrict access
10. **Regular backups** of database and model files

---

## Monitoring and Maintenance

### Health Checks

- Backend: `http://your-domain.com/health`
- Monitor server logs regularly
- Set up uptime monitoring (UptimeRobot, Pingdom)

### Performance Monitoring

- Use tools like New Relic, Datadog, or Sentry
- Monitor API response times
- Track error rates

### Backup Strategy

- Daily database backups
- Backup model files
- Keep backups off-site

---

## Support

For issues or questions:
- Check logs in `/var/log/` or application logs
- Review Android Studio build logs
- Check browser console for frontend errors
