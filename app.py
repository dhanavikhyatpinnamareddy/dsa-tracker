import os
import psycopg2
from psycopg2.extras import RealDictCursor
import bcrypt
import random
import uuid
import secrets
import re
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, request, jsonify, session, g, redirect, send_from_directory
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Load environment variables
load_dotenv()

# Setup logging directories
os.makedirs('logs', exist_ok=True)
os.makedirs('static/uploads', exist_ok=True)

# Logger configurations
def setup_logger(name, log_file, level=logging.INFO):
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler = RotatingFileHandler(os.path.join('logs', log_file), maxBytes=5*1024*1024, backupCount=3)
    handler.setFormatter(formatter)
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:
        logger.addHandler(handler)
    return logger

auth_logger = setup_logger('auth', 'auth.log')
error_logger = setup_logger('error', 'error.log', logging.ERROR)
admin_logger = setup_logger('admin', 'admin.log')
security_logger = setup_logger('security', 'security.log')
rate_limit_logger = setup_logger('rate_limit', 'rate_limit.log')

# Flask App Initialisation
app = Flask(__name__, static_folder='static', static_url_path='')
app.secret_key = os.environ.get('SECRET_KEY', 'dsa_progress_tracker_secret_key_2026')

# Secure Session Settings
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.environ.get('FLASK_ENV') == 'production',
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
    MAX_CONTENT_LENGTH=5 * 1024 * 1024 # 5MB limit
)

# Reverse Proxy compatibility
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

# Rate Limiter Setup
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["300 per day", "100 per hour"],
    storage_uri="memory://",
    headers_enabled=True
)

# Custom limit exceeded logger
@app.errorhandler(429)
def ratelimit_handler(e):
    ip = get_remote_address()
    rate_limit_logger.warning(f"Rate limit exceeded by IP: {ip} - Route: {request.path}")
    return jsonify({"error": "Too many requests. Please try again later."}), 429

# CORS setup
cors_origins = os.environ.get('CORS_ORIGINS', '*').split(',')
CORS(app, origins=cors_origins, supports_credentials=True)

# Database schema migrations
def run_migrations():
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("[Migrations Warning] DATABASE_URL is not set. Skipping migrations.", flush=True)
        return
    try:
        db = psycopg2.connect(url)
        cursor = db.cursor()
        
        # 1. Users table migrations
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_attempts INTEGER DEFAULT 0;")
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP WITH TIME ZONE;")
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS session_version INTEGER DEFAULT 1;")
        
        # Clean up old flags and indexes from active tables
        cursor.execute("ALTER TABLE problems DROP COLUMN IF EXISTS is_deleted;")
        cursor.execute("ALTER TABLE problems DROP COLUMN IF EXISTS deleted_at;")
        cursor.execute("ALTER TABLE plans DROP COLUMN IF EXISTS is_deleted;")
        cursor.execute("ALTER TABLE plans DROP COLUMN IF EXISTS deleted_at;")
        cursor.execute("DROP INDEX IF EXISTS idx_problems_is_deleted;")
        cursor.execute("DROP INDEX IF EXISTS idx_plans_is_deleted;")
        
        # Problems active table migrations
        cursor.execute("ALTER TABLE problems ADD COLUMN IF NOT EXISTS attachment_url TEXT;")
        
        # Create archive table deleted_problems
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS deleted_problems (
                id VARCHAR(255) PRIMARY KEY,
                user_id INT NOT NULL,
                name VARCHAR(255) NOT NULL,
                difficulty VARCHAR(50) NOT NULL,
                platform VARCHAR(255) NOT NULL,
                topic VARCHAR(255) NOT NULL,
                date VARCHAR(50) NOT NULL,
                url TEXT,
                notes TEXT,
                attachment_url TEXT,
                associated_plans TEXT,
                deleted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        ''')
        
        # Create archive table deleted_plans
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS deleted_plans (
                id VARCHAR(255) PRIMARY KEY,
                user_id INT NOT NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                target_count INT NOT NULL,
                color VARCHAR(50) NOT NULL,
                deleted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        ''')
        
        # Create user indexes on active tables
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_problems_user_id ON problems(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_plans_user_id ON plans(user_id);")
        
        db.commit()
        cursor.close()
        db.close()
        print("[Migrations] Database schema migrations completed successfully.", flush=True)
    except Exception as e:
        print(f"[Migrations Error] Failed to run migrations: {str(e)}", flush=True)

# Run database migrations immediately
run_migrations()





# -------------------------------------------------------------
# Database Utility & Setup
# -------------------------------------------------------------
def get_db():
    db = getattr(g, "_database", None)

    if db is None:
        db = g._database = psycopg2.connect(
            os.environ["DATABASE_URL"],
            cursor_factory=RealDictCursor
        )

    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        try:
            db = get_db()
            cursor = db.cursor()
            
            # Create users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    is_admin INTEGER DEFAULT 0,
                    daily_target INTEGER DEFAULT 3,
                    email VARCHAR(255),
                    phone VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Add email and phone columns dynamically if they do not exist (for existing tables)
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN email VARCHAR(255)")
            except Exception as e:
                if e.args[0] != 1060: # 1060 = duplicate column name
                    raise e
                    
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN phone VARCHAR(50)")
            except Exception as e:
                if e.args[0] != 1060: # 1060 = duplicate column name
                    raise e
            
            # Create problems table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS problems (
                    id VARCHAR(255) PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    difficulty VARCHAR(50) NOT NULL,
                    platform VARCHAR(255) NOT NULL,
                    topic VARCHAR(255) NOT NULL,
                    date VARCHAR(50) NOT NULL,
                    url TEXT,
                    notes TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            ''')
            
            # Create plans table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS plans (
                    id VARCHAR(255) PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    description TEXT,
                    target_count INTEGER NOT NULL,
                    color VARCHAR(50) NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            ''')
            
            # Create problem_plans many-to-many lookup table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS problem_plans (
                    problem_id VARCHAR(255) NOT NULL,
                    plan_id VARCHAR(255) NOT NULL,
                    PRIMARY KEY (problem_id, plan_id),
                    FOREIGN KEY(problem_id) REFERENCES problems(id) ON DELETE CASCADE,
                    FOREIGN KEY(plan_id) REFERENCES plans(id) ON DELETE CASCADE
                )
            ''')
            
            # Create verification_codes table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS verification_codes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    target VARCHAR(255) NOT NULL,
                    code VARCHAR(50) NOT NULL,
                    purpose VARCHAR(50) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            db.commit()
            
            # Seed default admin user if it doesn't exist
            cursor.execute("SELECT * FROM users WHERE username = 'admin'")
            if not cursor.fetchone():
                hashed = bcrypt.hashpw('adminpassword'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                cursor.execute(
                    "INSERT INTO users (username, password_hash, is_admin, email, phone) VALUES (%s, %s, 1, %s, %s)",
                    ('admin', hashed, 'admin@dsa.com', '1234567890')
                )
                db.commit()
                print("Default admin account created: admin / adminpassword")
        except Exception as e:
            print(f"[DB Init Error] Failed to initialize database: {str(e)}", flush=True)

#init_db()

# -------------------------------------------------------------
# Input Validation & Sanitization Helpers
# -------------------------------------------------------------
def validate_username(username):
    if not username:
        return False
    return bool(re.match(r"^[a-zA-Z0-9_-]{3,30}$", username))

def validate_email(email):
    if not email:
        return False
    return bool(re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", email))

def validate_url(url):
    if not url:
        return True  # Optional field
    return bool(re.match(r"^https?://[^\s/$.?#].[^\s]*$", url))

def is_strong_password(password):
    if len(password) < 8:
        return False
    if not re.search(r"[A-Za-z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    return True

def sanitize_text(text):
    if not text:
        return ""
    # Strip HTML tags to prevent XSS/injection
    clean = re.sub(r'<[^>]*>', '', text)
    return clean.strip()

# -------------------------------------------------------------
# Route Guards
# -------------------------------------------------------------
def get_current_user():
    if 'user_id' in session and 'session_version' in session:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT is_admin, session_version, locked_until FROM users WHERE id = %s", (session['user_id'],))
        row = cursor.fetchone()
        
        if row:
            # Check if account is locked
            if row['locked_until']:
                now = datetime.now(row['locked_until'].tzinfo) if row['locked_until'].tzinfo else datetime.now()
                if now < row['locked_until']:
                    session.clear()
                    return None
                    
            # Verify session version matches
            if row['session_version'] == session['session_version']:
                # Update session values if roles changed
                session['is_admin'] = row['is_admin']
                return {'id': session['user_id'], 'username': session['username'], 'is_admin': bool(row['is_admin'])}
                
        # If mismatch or user not found, invalidate session
        session.clear()
    return None


# -------------------------------------------------------------
# Frontend Static Asset Delivery
# -------------------------------------------------------------
@app.route('/')
def serve_index():
    return app.send_static_file('index.html')

# -------------------------------------------------------------
# Auth API Endpoints
# -------------------------------------------------------------
def send_otp_message(target, code, purpose):
    purpose_text = "creating your account" if purpose == 'signup' else "resetting your password"
    subject = "DSA Progress Tracker Verification Code"
    body = (
        f"Hello,\n\n"
        f"Your 6-digit verification code for {purpose_text} is: {code}\n\n"
        f"This code is valid for 5 minutes.\n\n"
        f"Happy coding,\n"
        f"DSA Progress Tracker Team"
    )
    
    resend_api_key = os.environ.get('RESEND_API_KEY')
    sendgrid_api_key = os.environ.get('SENDGRID_API_KEY')
    mailgun_api_key = os.environ.get('MAILGUN_API_KEY')
    brevo_api_key = os.environ.get('BREVO_API_KEY')
    
    import requests
    
    # 1. Try Brevo HTTP API
    if brevo_api_key:
        from_email = os.environ.get('BREVO_FROM_EMAIL', 'no-reply@dsa-tracker.com')
        try:
            headers = {
                "api-key": brevo_api_key,
                "Content-Type": "application/json",
                "accept": "application/json"
            }
            payload = {
                "sender": {"name": "DSA Progress Tracker", "email": from_email},
                "to": [{"email": target}],
                "subject": subject,
                "textContent": body
            }
            response = requests.post("https://api.brevo.com/v3/smtp/email", json=payload, headers=headers)
            if response.status_code in (200, 201, 202):
                print(f"[Brevo Success] Sent OTP '{code}' to '{target}' for '{purpose}'", flush=True)
                return True
            else:
                print(f"[Brevo Error] API returned status {response.status_code}: {response.text}", flush=True)
        except Exception as e:
            print(f"[Brevo Exception] Failed to send email: {str(e)}", flush=True)
            
    # 2. Try Resend HTTP API
    elif resend_api_key:
        from_email = os.environ.get('RESEND_FROM_EMAIL', 'onboarding@resend.dev')
        try:
            headers = {
                "Authorization": f"Bearer {resend_api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "from": from_email,
                "to": [target],
                "subject": subject,
                "text": body
            }
            response = requests.post("https://api.resend.com/emails", json=payload, headers=headers)
            if response.status_code in (200, 201):
                print(f"[Resend Success] Sent OTP '{code}' to '{target}' for '{purpose}'", flush=True)
                return True
            else:
                print(f"[Resend Error] API returned status {response.status_code}: {response.text}", flush=True)
        except Exception as e:
            print(f"[Resend Exception] Failed to send email: {str(e)}", flush=True)
            
    # 3. Try SendGrid HTTP API
    elif sendgrid_api_key:
        from_email = os.environ.get('SENDGRID_FROM_EMAIL', 'no-reply@dsa-tracker.com')
        try:
            headers = {
                "Authorization": f"Bearer {sendgrid_api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "personalizations": [{"to": [{"email": target}]}],
                "from": {"email": from_email},
                "subject": subject,
                "content": [{"type": "text/plain", "value": body}]
            }
            response = requests.post("https://api.sendgrid.com/v3/mail/send", json=payload, headers=headers)
            if response.status_code in (200, 202):
                print(f"[SendGrid Success] Sent OTP '{code}' to '{target}' for '{purpose}'", flush=True)
                return True
            else:
                print(f"[SendGrid Error] API returned status {response.status_code}: {response.text}", flush=True)
        except Exception as e:
            print(f"[SendGrid Exception] Failed to send email: {str(e)}", flush=True)
            
    # 4. Try Mailgun HTTP API
    elif mailgun_api_key:
        domain = os.environ.get('MAILGUN_DOMAIN')
        from_email = os.environ.get('MAILGUN_FROM_EMAIL', f"no-reply@{domain}" if domain else "no-reply@dsa-tracker.com")
        if domain:
            try:
                response = requests.post(
                    f"https://api.mailgun.net/v3/{domain}/messages",
                    auth=("api", mailgun_api_key),
                    data={"from": from_email, "to": [target], "subject": subject, "text": body}
                )
                if response.status_code == 200:
                    print(f"[Mailgun Success] Sent OTP '{code}' to '{target}' for '{purpose}'", flush=True)
                    return True
                else:
                    print(f"[Mailgun Error] API returned status {response.status_code}: {response.text}", flush=True)
            except Exception as e:
                print(f"[Mailgun Exception] Failed to send email: {str(e)}", flush=True)
        else:
            print("[Mailgun Warning] MAILGUN_DOMAIN env variable is missing.", flush=True)
            
    else:
        print("[Email Warning] No email API provider keys (BREVO_API_KEY, RESEND_API_KEY, SENDGRID_API_KEY, MAILGUN_API_KEY) configured. Falling back to console.", flush=True)
            
    # Fallback console log for local development
    print(f"\n[VERIFICATION CODE FALLBACK] Sent code '{code}' to '{target}' for '{purpose}'\n", flush=True)
    return False

@app.route('/api/auth/send-code', methods=['POST'])
@limiter.limit("3 per 10 minutes")
def send_code():
    data = request.json or {}
    username = (data.get('username') or '').strip()
    target = (data.get('target') or '').strip()
    purpose = data.get('purpose')
    
    if not target or purpose not in ('signup', 'reset'):
        return jsonify({'error': 'Target and valid purpose are required.'}), 400
        
    if not validate_email(target):
        return jsonify({'error': 'Invalid email address.'}), 400
        
    db = get_db()
    cursor = db.cursor()
    
    if purpose == 'signup':
        if not username or not validate_username(username):
            return jsonify({'error': 'Username is required and must be alphanumeric (3-30 chars).'}), 400
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            return jsonify({'error': 'Username is already taken.'}), 400
    else:  # reset
        if not username:
            return jsonify({'error': 'Username is required.'}), 400
        cursor.execute("SELECT id, email FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        if not user:
            return jsonify({'error': 'Username not found.'}), 404
        
        db_email = user['email']
        match = False
        if db_email and db_email.strip().lower() == target.lower():
            match = True
            
        if not match:
            return jsonify({'error': 'Verification target does not match registered email.'}), 400
            
    # Generate 6-digit random code
    code = f"{random.randint(100000, 999999)}"
    
    # Store code (delete old codes for this target first to keep it clean)
    cursor.execute("DELETE FROM verification_codes WHERE target = %s AND purpose = %s", (target, purpose))
    cursor.execute(
        "INSERT INTO verification_codes (target, code, purpose, created_at) VALUES (%s, %s, %s, CURRENT_TIMESTAMP)",
        (target, code, purpose)
    )
    db.commit()
    
    # Try sending via real service, fallback to console log
    sent_real = send_otp_message(target, code, purpose)
    
    auth_logger.info(f"Verification code sent to {target} for {purpose}. Real: {sent_real}")
    
    return jsonify({
        'message': 'Verification code sent successfully.',
        'sent_real': sent_real
    })

@app.route('/api/auth/signup', methods=['POST'])
@limiter.limit("5 per hour")
def signup():
    data = request.json or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    email = (data.get('email') or '').strip()
    code = (data.get('code') or '').strip()
    
    if not validate_username(username):
        return jsonify({'error': 'Username must be 3-30 chars and contain only letters, numbers, underscores or hyphens.'}), 400
        
    if not validate_email(email):
        return jsonify({'error': 'Invalid email address.'}), 400
        
    if not is_strong_password(password):
        return jsonify({'error': 'Password must be at least 8 characters and contain at least one letter and one number.'}), 400
        
    if not code:
        return jsonify({'error': 'Verification code is required.'}), 400
        
    db = get_db()
    cursor = db.cursor()
    
    # Check if username exists
    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
    if cursor.fetchone():
        return jsonify({'error': 'Username is already taken.'}), 400
        
    # Check verification code matches
    cursor.execute(
        "SELECT code, created_at FROM verification_codes WHERE target = %s AND purpose = 'signup' ORDER BY id DESC LIMIT 1",
        (email,)
    )
    row = cursor.fetchone()
    
    if not row or row['code'] != code:
        return jsonify({'error': 'Wrong verification code.'}), 400
        
    # Check expiration (5 minutes)
    now = datetime.now(row['created_at'].tzinfo) if row['created_at'].tzinfo else datetime.now()
    if (now - row['created_at']).total_seconds() > 300:
        return jsonify({'error': 'Verification code expired.'}), 400
        
    try:
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cursor.execute(
            "INSERT INTO users (username, password_hash, email, phone, session_version) VALUES (%s, %s, %s, %s, 1)",
            (username, hashed, email, '')
        )
        
        # Delete verification codes for this target
        cursor.execute("DELETE FROM verification_codes WHERE target = %s", (email,))
        db.commit()
        
        # Log user in directly
        cursor.execute("SELECT id, username, is_admin, session_version FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        
        # Session regeneration to prevent fixation
        session.clear()
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['is_admin'] = user['is_admin']
        session['session_version'] = user['session_version']
        session['csrf_token'] = secrets.token_hex(32)
        
        auth_logger.info(f"User signed up and logged in: {username} ({email}) from IP: {get_remote_address()}")
        
        return jsonify({
            'message': 'Signup successful',
            'csrf_token': session['csrf_token'],
            'user': {'username': user['username'], 'is_admin': bool(user['is_admin']), 'daily_target': 3}
        }), 201
    except Exception as e:
        db.rollback()
        error_logger.error(f"[Signup Error] failed for user {username}: {str(e)}")
        return jsonify({'error': 'Username is already taken.'}), 400

@app.route('/api/auth/login', methods=['POST'])
@limiter.limit("5 per minute; 20 per hour")
def login():
    data = request.json or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    
    if not username or not password:
        return jsonify({'error': 'Username and password are required.'}), 400
        
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    
    if not user:
        auth_logger.warning(f"Failed login attempt for non-existent username: {username} from IP: {get_remote_address()}")
        return jsonify({'error': 'Invalid username or password.'}), 401
        
    # Check if locked out
    if user['locked_until']:
        now = datetime.now(user['locked_until'].tzinfo) if user['locked_until'].tzinfo else datetime.now()
        if now < user['locked_until']:
            locked_remaining = int((user['locked_until'] - now).total_seconds() / 60)
            auth_logger.warning(f"Login attempt on locked account: {username} from IP: {get_remote_address()}")
            return jsonify({'error': f'Account locked due to too many failed attempts. Try again in {locked_remaining} minutes.'}), 423
            
    # Check password
    if bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
        # Success!
        session.clear()
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['is_admin'] = user['is_admin']
        session['session_version'] = user['session_version'] if user['session_version'] is not None else 1
        session['csrf_token'] = secrets.token_hex(32)
        
        # Reset failed attempts
        cursor.execute("UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE id = %s", (user['id'],))
        db.commit()
        
        auth_logger.info(f"User logged in successfully: {username} from IP: {get_remote_address()}")
        
        return jsonify({
            'message': 'Login successful',
            'csrf_token': session['csrf_token'],
            'user': {
                'username': user['username'],
                'is_admin': bool(user['is_admin']),
                'daily_target': user['daily_target']
            }
        })
    else:
        # Failure!
        failed_attempts = (user['failed_attempts'] or 0) + 1
        locked_until = None
        
        if failed_attempts >= 5:
            locked_until = datetime.now() + timedelta(minutes=15)
            auth_logger.warning(f"User account locked: {username} (5 failed attempts) from IP: {get_remote_address()}")
            
        cursor.execute("UPDATE users SET failed_attempts = %s, locked_until = %s WHERE id = %s", (failed_attempts, locked_until, user['id']))
        db.commit()
        
        auth_logger.warning(f"Failed login attempt for user: {username} (Failed count: {failed_attempts}) from IP: {get_remote_address()}")
        
        if failed_attempts >= 5:
            return jsonify({'error': 'Account locked due to too many failed attempts. Try again in 15 minutes.'}), 423
            
        return jsonify({'error': 'Invalid username or password.'}), 401

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    user = get_current_user()
    username = user['username'] if user else "Unknown"
    session.clear()
    auth_logger.info(f"User logged out: {username} from IP: {get_remote_address()}")
    return jsonify({'message': 'Logged out successfully'})

@app.route('/api/auth/logout-all', methods=['POST'])
def logout_all():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
        
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE users SET session_version = session_version + 1 WHERE id = %s", (user['id'],))
    db.commit()
    
    auth_logger.info(f"User logged out from all devices: {user['username']} from IP: {get_remote_address()}")
    session.clear()
    return jsonify({'message': 'Logged out from all devices successfully.'})

@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    user = get_current_user()
    
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
        
    if user:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT daily_target FROM users WHERE id = %s", (user['id'],))
        row = cursor.fetchone()
        daily_target = row['daily_target'] if row else 3
        
        return jsonify({
            'authenticated': True,
            'csrf_token': session['csrf_token'],
            'user': {
                'username': user['username'],
                'is_admin': bool(user['is_admin']),
                'daily_target': daily_target
            }
        })
    return jsonify({
        'authenticated': False,
        'csrf_token': session['csrf_token']
    })

@app.route('/api/auth/reset-password', methods=['POST'])
@limiter.limit("5 per hour")
def reset_password():
    data = request.json or {}
    username = (data.get('username') or '').strip()
    verification = (data.get('verification') or '').strip()
    new_password = data.get('new_password') or ''
    code = (data.get('code') or '').strip()
    
    if not username or not verification or not code or not is_strong_password(new_password):
        return jsonify({'error': 'Username, verification email, code, and a strong new password (min 8 chars, 1 letter, 1 number) are required.'}), 400
        
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, email FROM users WHERE username = %s", (username,))
    row = cursor.fetchone()
    
    if not row:
        return jsonify({'error': 'Username not found.'}), 404
        
    db_email = row['email']
    
    match = False
    if db_email and db_email.strip().lower() == verification.lower():
        match = True
        
    if not match:
        return jsonify({'error': 'Verification failed. Registered email does not match.'}), 400
        
    # Check verification code matches
    cursor.execute(
        "SELECT code, created_at FROM verification_codes WHERE target = %s AND purpose = 'reset' ORDER BY id DESC LIMIT 1",
        (verification,)
    )
    code_row = cursor.fetchone()
    if not code_row or code_row['code'] != code:
        return jsonify({'error': 'Wrong verification code.'}), 400
        
    # Check expiration (5 minutes)
    now = datetime.now(code_row['created_at'].tzinfo) if code_row['created_at'].tzinfo else datetime.now()
    if (now - code_row['created_at']).total_seconds() > 300:
        return jsonify({'error': 'Verification code expired.'}), 400
        
    hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    cursor.execute("UPDATE users SET password_hash = %s, session_version = session_version + 1 WHERE id = %s", (hashed, row['id']))
    cursor.execute("DELETE FROM verification_codes WHERE target = %s", (verification,))
    db.commit()
    
    auth_logger.info(f"Password reset successfully for user: {username} from IP: {get_remote_address()}")
    
    return jsonify({'message': 'Password reset successfully.'})

# -------------------------------------------------------------
# User Settings APIs
# -------------------------------------------------------------
@app.route('/api/user/settings', methods=['POST'])
def save_settings():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.json or {}
    username = (data.get('username') or '').strip()
    daily_target = data.get('daily_target')
    
    if not validate_username(username) or daily_target is None:
        return jsonify({'error': 'Username (3-30 chars, alphanumeric/dash/underscore) and Daily Target are required.'}), 400
        
    db = get_db()
    cursor = db.cursor()
    
    try:
        cursor.execute(
            "UPDATE users SET username = %s, daily_target = %s WHERE id = %s",
            (username, int(daily_target), user['id'])
        )
        db.commit()
        session['username'] = username
        
        admin_logger.info(f"User {user['username']} updated settings to: username={username}, target={daily_target}")
        
        return jsonify({'message': 'Settings updated successfully'})
    except Exception as e:
        db.rollback()
        error_logger.error(f"Error updating settings for {user['username']}: {str(e)}")
        return jsonify({'error': 'Username is already taken.'}), 400

# -------------------------------------------------------------
# DSA Problems CRUD APIs
# -------------------------------------------------------------
@app.route('/api/problems', methods=['GET'])
def get_problems():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
        
    db = get_db()
    cursor = db.cursor()
    
    # Retrieve all user problems
    cursor.execute("SELECT * FROM problems WHERE user_id = %s ORDER BY date DESC, id DESC", (user['id'],))
    problem_rows = cursor.fetchall()
    
    # Retrieve mappings of problems to study plans
    cursor.execute('''
        SELECT pp.problem_id, pp.plan_id 
        FROM problem_plans pp
        JOIN plans p ON pp.plan_id = p.id
        WHERE p.user_id = %s
    ''', (user['id'],))
    mapping_rows = cursor.fetchall()
    
    mappings = {}
    for row in mapping_rows:
        pid = row['problem_id']
        plan_id = row['plan_id']
        if pid not in mappings:
            mappings[pid] = []
        mappings[pid].append(plan_id)
        
    problems = []
    for row in problem_rows:
        pid = row['id']
        problems.append({
            'id': pid,
            'name': row['name'],
            'difficulty': row['difficulty'],
            'platform': row['platform'],
            'topic': row['topic'],
            'date': row['date'],
            'url': row['url'],
            'notes': row['notes'],
            'attachment_url': row.get('attachment_url', ''),
            'plans': mappings.get(pid, [])
        })
        
    return jsonify(problems)

@app.route('/api/problems', methods=['POST'])
def save_problem():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.json or {}
    pid = data.get('id')
    name = sanitize_text(data.get('name') or '')
    difficulty = sanitize_text(data.get('difficulty') or '')
    platform = sanitize_text(data.get('platform') or '')
    topic = sanitize_text(data.get('topic') or '')
    date = sanitize_text(data.get('date') or '')
    url = sanitize_text(data.get('url') or '')
    notes = sanitize_text(data.get('notes') or '')
    attachment_url = sanitize_text(data.get('attachment_url') or '')
    associated_plans = data.get('plans') or [] # List of plan IDs
    
    if not name or not difficulty or not platform or not topic or not date:
        return jsonify({'error': 'Missing required problem fields.'}), 400
        
    if not validate_url(url):
        return jsonify({'error': 'Invalid URL format.'}), 400
        
    db = get_db()
    cursor = db.cursor()
    
    if pid:
        # Check ownership of editing entry
        cursor.execute("SELECT * FROM problems WHERE id = %s AND user_id = %s", (pid, user['id']))
        if not cursor.fetchone():
            return jsonify({'error': 'Problem log not found or unauthorized.'}), 404
            
        # Update existing
        cursor.execute('''
            UPDATE problems 
            SET name = %s, difficulty = %s, platform = %s, topic = %s, date = %s, url = %s, notes = %s, attachment_url = %s
            WHERE id = %s AND user_id = %s
        ''', (name, difficulty, platform, topic, date, url, notes, attachment_url, pid, user['id']))
    else:
        # Check if the same problem already exists
        cursor.execute("""
            SELECT id
            FROM problems
            WHERE user_id = %s
            AND name = %s
            AND platform = %s
        """, (user['id'], name, platform))

        if cursor.fetchone():
            return jsonify({
                "error": "This problem is already logged."
            }), 409

        # Create new problem
        pid = f"prob-{int(bcrypt.gensalt()[4:12].hex(), 16)}"

        cursor.execute("""
            INSERT INTO problems
            (id, user_id, name, difficulty, platform, topic, date, url, notes, attachment_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            pid,
            user['id'],
            name,
            difficulty,
            platform,
            topic,
            date,
            url,
            notes,
            attachment_url
        ))
        
    # Sync plans mappings: delete old mappings for this problem
    cursor.execute("DELETE FROM problem_plans WHERE problem_id = %s", (pid,))
    
    # Insert checked plan mappings (making sure they belong to current user)
    for plan_id in associated_plans:
        cursor.execute("SELECT id FROM plans WHERE id = %s AND user_id = %s", (plan_id, user['id']))
        if cursor.fetchone():
            cursor.execute(
                "INSERT INTO problem_plans (problem_id, plan_id) VALUES (%s, %s)",
                (pid, plan_id)
            )
            
    db.commit()
    return jsonify({'message': 'Problem saved successfully', 'id': pid})

@app.route('/api/problems/<pid>', methods=['DELETE'])
def delete_problem(pid):
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
        
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("SELECT * FROM problems WHERE id = %s AND user_id = %s", (pid, user['id']))
    problem = cursor.fetchone()
    if not problem:
        return jsonify({'error': 'Problem log not found or unauthorized.'}), 404
        
    # Get associated plans
    cursor.execute("SELECT plan_id FROM problem_plans WHERE problem_id = %s", (pid,))
    plan_ids = [row['plan_id'] for row in cursor.fetchall()]
    associated_plans_str = ','.join(plan_ids)
    
    # Archive into deleted_problems
    cursor.execute('''
        INSERT INTO deleted_problems 
        (id, user_id, name, difficulty, platform, topic, date, url, notes, attachment_url, associated_plans)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ''', (
        problem['id'],
        problem['user_id'],
        problem['name'],
        problem['difficulty'],
        problem['platform'],
        problem['topic'],
        problem['date'],
        problem['url'],
        problem['notes'],
        problem['attachment_url'],
        associated_plans_str
    ))
    
    # Physically delete from problems
    cursor.execute("DELETE FROM problems WHERE id = %s", (pid,))
    db.commit()
    return jsonify({'message': 'Problem log soft-deleted successfully'})

@app.route('/api/problems/bulk-delete', methods=['POST'])
def bulk_delete_problems():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.json or {}
    ids = data.get('ids') or []
    
    if not ids:
        return jsonify({'error': 'No IDs provided'}), 400
        
    db = get_db()
    cursor = db.cursor()
    
    # Validate and select all problems belonging to the user
    placeholders = ','.join('%s' for _ in ids)
    cursor.execute(
        f"SELECT * FROM problems WHERE id IN ({placeholders}) AND user_id = %s",
        (*ids, user['id'])
    )
    problems = cursor.fetchall()
    
    if not problems:
        return jsonify({'error': 'No valid active problems to delete'}), 400
        
    for problem in problems:
        pid = problem['id']
        # Get associated plans
        cursor.execute("SELECT plan_id FROM problem_plans WHERE problem_id = %s", (pid,))
        plan_ids = [row['plan_id'] for row in cursor.fetchall()]
        associated_plans_str = ','.join(plan_ids)
        
        # Archive
        cursor.execute('''
            INSERT INTO deleted_problems 
            (id, user_id, name, difficulty, platform, topic, date, url, notes, attachment_url, associated_plans)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            problem['id'],
            problem['user_id'],
            problem['name'],
            problem['difficulty'],
            problem['platform'],
            problem['topic'],
            problem['date'],
            problem['url'],
            problem['notes'],
            problem['attachment_url'],
            associated_plans_str
        ))
        
        # Delete from problems
        cursor.execute("DELETE FROM problems WHERE id = %s", (pid,))
        
    db.commit()
    return jsonify({'message': f'Successfully soft-deleted {len(problems)} problem logs.'})

# -------------------------------------------------------------
# Study Plans APIs
# -------------------------------------------------------------
@app.route('/api/plans', methods=['GET'])
def get_plans():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
        
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM plans WHERE user_id = %s ORDER BY id DESC", (user['id'],))
    plan_rows = cursor.fetchall()
    
    plans = []
    for row in plan_rows:
        plans.append({
            'id': row['id'],
            'title': row['title'],
            'description': row['description'],
            'targetCount': row['target_count'],
            'color': row['color']
        })
    return jsonify(plans)

@app.route('/api/plans', methods=['POST'])
def save_plan():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.json or {}
    title = sanitize_text(data.get('title') or '')
    description = sanitize_text(data.get('description') or '')
    target_count = data.get('targetCount')
    color = sanitize_text(data.get('color') or '')
    
    if not title or target_count is None or not color:
        return jsonify({'error': 'Missing study plan fields'}), 400
        
    db = get_db()
    cursor = db.cursor()
    
    plan_id = f"plan-{int(bcrypt.gensalt()[4:12].hex(), 16)}"
    cursor.execute('''
        INSERT INTO plans (id, user_id, title, description, target_count, color)
        VALUES (%s, %s, %s, %s, %s, %s)
    ''', (plan_id, user['id'], title, description, int(target_count), color))
    db.commit()
    
    return jsonify({'message': 'Study plan created successfully', 'id': plan_id})

@app.route('/api/plans/<plan_id>', methods=['DELETE'])
def delete_plan(plan_id):
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
        
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("SELECT * FROM plans WHERE id = %s AND user_id = %s", (plan_id, user['id']))
    plan = cursor.fetchone()
    if not plan:
        return jsonify({'error': 'Study plan not found or unauthorized.'}), 404
        
    # Archive into deleted_plans
    cursor.execute('''
        INSERT INTO deleted_plans (id, user_id, title, description, target_count, color)
        VALUES (%s, %s, %s, %s, %s, %s)
    ''', (
        plan['id'],
        plan['user_id'],
        plan['title'],
        plan['description'],
        plan['target_count'],
        plan['color']
    ))
    
    # Physically delete from plans
    cursor.execute("DELETE FROM plans WHERE id = %s", (plan_id,))
    db.commit()
    return jsonify({'message': 'Study plan soft-deleted successfully'})

# -------------------------------------------------------------
# User Data Reset APIs
# -------------------------------------------------------------
@app.route('/api/user/reset', methods=['POST'])
def reset_progress():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.json or {}
    scope = data.get('scope')
    
    db = get_db()
    cursor = db.cursor()
    
    if scope in ("problems", "all"):
        # Select all active problems
        cursor.execute("SELECT * FROM problems WHERE user_id = %s", (user['id'],))
        problems = cursor.fetchall()
        for problem in problems:
            pid = problem['id']
            cursor.execute("SELECT plan_id FROM problem_plans WHERE problem_id = %s", (pid,))
            plan_ids = [row['plan_id'] for row in cursor.fetchall()]
            associated_plans_str = ','.join(plan_ids)
            
            cursor.execute('''
                INSERT INTO deleted_problems 
                (id, user_id, name, difficulty, platform, topic, date, url, notes, attachment_url, associated_plans)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                problem['id'],
                problem['user_id'],
                problem['name'],
                problem['difficulty'],
                problem['platform'],
                problem['topic'],
                problem['date'],
                problem['url'],
                problem['notes'],
                problem['attachment_url'],
                associated_plans_str
            ))
        cursor.execute("DELETE FROM problems WHERE user_id = %s", (user['id'],))
        
    if scope in ("plans", "all"):
        cursor.execute("SELECT * FROM plans WHERE user_id = %s", (user['id'],))
        plans = cursor.fetchall()
        for plan in plans:
            cursor.execute('''
                INSERT INTO deleted_plans (id, user_id, title, description, target_count, color)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (
                plan['id'],
                plan['user_id'],
                plan['title'],
                plan['description'],
                plan['target_count'],
                plan['color']
            ))
        cursor.execute("DELETE FROM plans WHERE user_id = %s", (user['id'],))
        
    if scope == "all":
        cursor.execute("UPDATE users SET daily_target = 3 WHERE id = %s", (user['id'],))
        
    db.commit()
    
    if scope == "problems":
        return jsonify({'message': 'All active problem logs soft-deleted successfully.'})
    elif scope == "plans":
        return jsonify({'message': 'All customized study plans soft-deleted successfully.'})
    elif scope == "all":
        return jsonify({'message': 'Entire active application data soft-reset successfully.'})
        
    return jsonify({'error': 'Invalid reset scope'}), 400

# -------------------------------------------------------------
# Trash, Restore, and Permanent Deletion APIs
# -------------------------------------------------------------
@app.route('/api/trash', methods=['GET'])
def get_trash():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
        
    db = get_db()
    cursor = db.cursor()
    
    if user['is_admin']:
        # Admin can view all soft-deleted items across all users
        cursor.execute('''
            SELECT p.*, u.username as owner_username 
            FROM deleted_problems p 
            JOIN users u ON p.user_id = u.id 
            ORDER BY p.deleted_at DESC
        ''')
        problems = cursor.fetchall()
        
        cursor.execute('''
            SELECT pl.*, u.username as owner_username 
            FROM deleted_plans pl 
            JOIN users u ON pl.user_id = u.id 
            ORDER BY pl.deleted_at DESC
        ''')
        plans = cursor.fetchall()
    else:
        # Regular user views their own soft-deleted items
        cursor.execute("SELECT * FROM deleted_problems WHERE user_id = %s ORDER BY deleted_at DESC", (user['id'],))
        problems = cursor.fetchall()
        
        cursor.execute("SELECT * FROM deleted_plans WHERE user_id = %s ORDER BY deleted_at DESC", (user['id'],))
        plans = cursor.fetchall()
        
    return jsonify({
        'problems': problems,
        'plans': plans
    })

@app.route('/api/trash/restore/<item_type>/<item_id>', methods=['POST'])
def restore_trash(item_type, item_id):
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
        
    if item_type not in ('problem', 'plan'):
        return jsonify({'error': 'Invalid item type.'}), 400
        
    db = get_db()
    cursor = db.cursor()
    table = 'deleted_problems' if item_type == 'problem' else 'deleted_plans'
    
    # Verify ownership or admin privileges
    if user['is_admin']:
        cursor.execute(f"SELECT * FROM {table} WHERE id = %s", (item_id,))
    else:
        cursor.execute(f"SELECT * FROM {table} WHERE id = %s AND user_id = %s", (item_id, user['id']))
        
    item = cursor.fetchone()
    if not item:
        return jsonify({'error': 'Soft-deleted item not found.'}), 404
        
    if item_type == 'problem':
        cursor.execute('''
            INSERT INTO problems (id, user_id, name, difficulty, platform, topic, date, url, notes, attachment_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            item['id'],
            item['user_id'],
            item['name'],
            item['difficulty'],
            item['platform'],
            item['topic'],
            item['date'],
            item['url'],
            item['notes'],
            item['attachment_url']
        ))
        
        if item['associated_plans']:
            plan_ids = item['associated_plans'].split(',')
            for plan_id in plan_ids:
                cursor.execute("SELECT id FROM plans WHERE id = %s", (plan_id,))
                if cursor.fetchone():
                    cursor.execute(
                        "INSERT INTO problem_plans (problem_id, plan_id) VALUES (%s, %s)",
                        (item['id'], plan_id)
                    )
        cursor.execute("DELETE FROM deleted_problems WHERE id = %s", (item_id,))
    else:
        cursor.execute('''
            INSERT INTO plans (id, user_id, title, description, target_count, color)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (
            item['id'],
            item['user_id'],
            item['title'],
            item['description'],
            item['target_count'],
            item['color']
        ))
        cursor.execute("DELETE FROM deleted_plans WHERE id = %s", (item_id,))
        
    db.commit()
    admin_logger.info(f"Item '{item_id}' ({item_type}) restored by {user['username']}.")
    return jsonify({'message': f'{item_type.capitalize()} restored successfully.'})

@app.route('/api/trash/permanent/<item_type>/<item_id>', methods=['DELETE'])
def permanent_delete(item_type, item_id):
    user = get_current_user()
    if not user or not user['is_admin']:
        security_logger.warning(f"Unauthorized permanent delete attempt on '{item_id}' by user: {user['username'] if user else 'Guest'}")
        return jsonify({'error': 'Forbidden: Admin access required.'}), 403
        
    if item_type not in ('problem', 'plan'):
        return jsonify({'error': 'Invalid item type.'}), 400
        
    db = get_db()
    cursor = db.cursor()
    table = 'deleted_problems' if item_type == 'problem' else 'deleted_plans'
    
    cursor.execute(f"SELECT id FROM {table} WHERE id = %s", (item_id,))
    if not cursor.fetchone():
        return jsonify({'error': 'Soft-deleted item not found.'}), 404
        
    cursor.execute(f"DELETE FROM {table} WHERE id = %s", (item_id,))
    db.commit()
    admin_logger.info(f"Item '{item_id}' ({item_type}) permanently deleted from database by Admin '{user['username']}'.")
    return jsonify({'message': f'{item_type.capitalize()} permanently deleted.'})

# -------------------------------------------------------------
# Secure File Upload Attachment API
# -------------------------------------------------------------
def check_file_signature(file_stream, filename):
    header = file_stream.read(4)
    file_stream.seek(0)
    
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    if ext == 'pdf':
        return header.startswith(b'%PDF')
    elif ext == 'png':
        return header.startswith(b'\x89PNG')
    elif ext in ('jpg', 'jpeg'):
        return header.startswith(b'\xff\xd8')
    return False

@app.route('/api/upload', methods=['POST'])
@limiter.limit("10 per hour")
def upload_file():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
        
    if 'file' not in request.files:
        return jsonify({'error': 'No file segment found.'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected.'}), 400
        
    # Check extension
    allowed_extensions = {'pdf', 'png', 'jpg', 'jpeg'}
    if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
        return jsonify({'error': 'Allowed file extensions: pdf, png, jpg, jpeg.'}), 400
        
    # Check mime type signature (magic numbers)
    if not check_file_signature(file.stream, file.filename):
        security_logger.warning(f"File upload blocked: signature mismatch in filename: {file.filename} by {user['username']}")
        return jsonify({'error': 'File type signature validation failed.'}), 400
        
    # Check file size (5MB maximum)
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    
    if size > 5 * 1024 * 1024:
        return jsonify({'error': 'Maximum file size allowed is 5MB.'}), 400
        
    # Rename file securely
    orig_ext = file.filename.rsplit('.', 1)[1].lower()
    new_filename = f"{uuid.uuid4().hex}.{orig_ext}"
    
    os.makedirs(os.path.join('static', 'uploads'), exist_ok=True)
    save_path = os.path.join('static', 'uploads', new_filename)
    file.save(save_path)
    
    return jsonify({
        'message': 'File uploaded successfully.',
        'url': f'/uploads/{new_filename}'
    })

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    # Safely serve files from uploads folder
    return send_from_directory(os.path.join('static', 'uploads'), filename)

# -------------------------------------------------------------
# SEO Static Asset Routing
# -------------------------------------------------------------
@app.route('/robots.txt')
def serve_robots():
    return send_from_directory(app.static_folder, 'robots.txt')

@app.route('/sitemap.xml')
def serve_sitemap():
    return send_from_directory(app.static_folder, 'sitemap.xml')

# -------------------------------------------------------------
# Admin Stats APIs
# -------------------------------------------------------------
@app.route('/api/admin/stats', methods=['GET'])
def get_admin_stats():
    user = get_current_user()
    if not user or not user['is_admin']:
        return jsonify({'error': 'Forbidden'}), 403
        
    db = get_db()
    cursor = db.cursor()
    
    # 1. Total users
    cursor.execute("SELECT COUNT(*) as count FROM users")
    total_users = cursor.fetchone()['count']
    
    # 2. Total active solved problems
    cursor.execute("SELECT COUNT(*) as count FROM problems")
    total_problems = cursor.fetchone()['count']
    
    # 3. User lists with registration date and active solve totals
    cursor.execute('''
        SELECT u.username, u.created_at, u.is_admin, COUNT(p.id) as solved_count
        FROM users u
        LEFT JOIN problems p ON u.id = p.user_id
        GROUP BY u.id
        ORDER BY solved_count DESC, u.username ASC
    ''')
    users_rows = cursor.fetchall()
    
    users_list = []
    for row in users_rows:
        users_list.append({
            'username': row['username'],
            'created_at': row['created_at'],
            'is_admin': bool(row['is_admin']),
            'solved_count': row['solved_count']
        })
        
    return jsonify({
        'total_users': total_users,
        'total_problems': total_problems,
        'users': users_list
    })

# -------------------------------------------------------------
# Security Headers & Redirect Hook
# -------------------------------------------------------------
@app.before_request
def redirect_to_https():
    if not app.debug and request.headers.get('X-Forwarded-Proto', 'http') != 'https':
        url = request.url.replace('http://', 'https://', 1)
        return redirect(url, code=301)

@app.after_request
def add_security_headers(response):
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), camera=(), microphone=()'
    
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self';"
    )
    
    response.headers['Server'] = 'DSA Tracker Secure Server'
    return response

# Global Error Handler to hide stack traces in production
@app.errorhandler(Exception)
def handle_exception(e):
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return jsonify({'error': e.description}), e.code
    
    # Log exception internally
    error_logger.error(f"Unhandled Exception: {str(e)}", exc_info=True)
    return jsonify({'error': 'An internal server error occurred.'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
