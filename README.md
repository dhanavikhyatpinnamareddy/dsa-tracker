
# Multi-User DSA Progress Tracker

A responsive, production-ready, and data-driven web application designed to help developers organize their Data Structures and Algorithms (DSA) preparation. It features secure multi-user authentication, email verification code (OTP) dispatch via modern HTTP REST APIs, interactive charts, and contribution activity heatmaps.

---

## 🚀 Key Features

* **Secure Onboarding**: User accounts with password hashing via `bcrypt` and strict registration verification.
* **HTTP API Email Verification**: Avoids outbound SMTP port blocking issues on cloud containers (e.g. Render/Cloud Run) by calling cloud mail providers (Resend, SendGrid, Mailgun) via HTTPS POST.
* **Interactive Dashboard**: Real-time stats panels including lifetime solved counts, active daily streaks, and circular daily target goal widgets.
* **Weekly Trends & Topic Analytics**: Dynamic charts mapping weekly practice volume and topic performance distributions.
* **Study Playlists**: Create custom study plans (e.g., *Trees Grind*, *LeetCode 75*) and attach logged questions directly to them.
* **Admin Dashboard**: Exposes global platform usage metrics and user registration databases.

---

## 🛠️ Technology Stack

* **Frontend**: HTML5, Vanilla CSS3 (responsive layout with glassmorphic theme elements), JavaScript, and `Chart.js` for data visualizations.
* **Backend**: Python 3.12, Flask, Gunicorn (production server), and `requests` (for HTTP API interactions).
* **Database**: PostgreSQL (via `psycopg2` with dict row factory) for production. Supports automatic local fallback to SQLite.

---

## ⚙️ Local Installation & Development

### 1. Prerequisites
* Python 3.12 or higher.
* PostgreSQL database service (optional; falls back to local SQLite database `dsa_tracker.db` automatically if credentials are not provided).

### 2. Clone and Setup Environment
Navigate to the project root directory and create a `.env` file based on `.env.example`:
```bash
cp .env.example .env
```
Open `.env` and configure:
```env
SECRET_KEY=generate_a_secure_session_secret
# To use PostgreSQL (optional, defaults to SQLite if left blank):
DATABASE_URL=postgresql://username:password@localhost:5432/dsa_tracker

# Setup your preferred HTTP email API provider (Resend is recommended):
RESEND_API_KEY=re_your_secret_key
RESEND_FROM_EMAIL=onboarding@resend.dev
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Development Server
```bash
python app.py
```
The server will start on **[http://localhost:5000](http://localhost:5000)**. Since the database auto-initializes on startup, the tables and default admin account will be seeded automatically.
* **Default Admin Account**: `admin` / `adminpassword`

---

## 🌐 Production Deployment

### 🐳 Containerization via Docker
A pre-configured `Dockerfile` is provided in the project root:
```dockerfile
FROM python:3.12-slim
ENV PYTHONUNBUFFERED True
WORKDIR /app
COPY . ./
RUN pip install --no-cache-dir -r requirements.txt
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app
```
To build and test the container image locally:
```bash
docker build -t dsa-tracker:latest .
docker run -p 5000:5000 --env PORT=5000 dsa-tracker:latest
```

### ☁️ Deploying to Render
1. Create a new **PostgreSQL Database** on Render. Copy its internal connection string.
2. Create a new **Web Service** on Render, linking it to your repository.
3. In the Render environment configurations, add the following variables:
   * `SECRET_KEY`: *random secure string*
   * `DATABASE_URL`: *paste your Render PostgreSQL database connection string*
   * `RESEND_API_KEY`: *your Resend API key*
   * `RESEND_FROM_EMAIL`: `onboarding@resend.dev` (or your verified domain sender)

### ☁️ Deploying to Google Cloud Run
Expose the app through Google Artifact Registry and run:
```bash
# Submit build to Cloud Build
gcloud builds submit --tag us-central1-docker.pkg.dev/[PROJECT_ID]/dsa-repo/dsa-app:latest

# Deploy to Cloud Run linking Cloud SQL
gcloud run deploy dsa-service \
    --image=us-central1-docker.pkg.dev/[PROJECT_ID]/dsa-repo/dsa-app:latest \
    --region=us-central1 \
    --add-cloudsql-instances=[PROJECT_ID]:us-central1:dsa-db-instance \
    --set-env-vars="DB_USER=postgres,DB_PASSWORD=[PASSWORD],DB_NAME=postgres,DB_HOST=/cloudsql/[PROJECT_ID]:us-central1:dsa-db-instance,SECRET_KEY=[SESSION_SECRET],RESEND_API_KEY=[API_KEY]" \
    --allow-unauthenticated
```

---

## 📁 Directory Structure

```
├── app.py                     # Main Flask application (APIs & verification routes)
├── requirements.txt           # Python application dependencies
├── Dockerfile                 # Container image specification
├── service.yaml               # Cloud Run deployment configuration
├── .env.example               # Environment variables configuration template
├── static/                    # Frontend assets folder
│   ├── index.html             # UI Layout (glassmorphism theme)
│   ├── app.js                 # Frontend API calls, routing, and Chart.js binding
│   └── styles.css             # CSS variables, layout grid rules, and theme styles
└── dsa_tracker_deployment.zip # Packaged deployment zip archive
```
