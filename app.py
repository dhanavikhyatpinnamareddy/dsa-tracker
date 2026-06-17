import os
import psycopg2
from psycopg2.extras import DictCursor
import bcrypt
import random
from dotenv import load_dotenv
from flask import Flask, request, jsonify, session, g
from flask_cors import CORS

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='static', static_url_path='')
app.secret_key = os.environ.get('SECRET_KEY', 'dsa_progress_tracker_secret_key_2026')
CORS(app, supports_credentials=True)

# -------------------------------------------------------------
# Database Utility & Setup
# -------------------------------------------------------------
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db_url = os.environ.get('DATABASE_URL')
        if db_url:
            db = g._database = psycopg2.connect(db_url, cursor_factory=DictCursor)
        else:
            db = g._database = psycopg2.connect(
                host=os.environ.get('DB_HOST', 'localhost'),
                port=os.environ.get('DB_PORT', '5432'),
                user=os.environ.get('DB_USER', 'postgres'),
                password=os.environ.get('DB_PASSWORD', ''),
                database=os.environ.get('DB_NAME', 'postgres'),
                cursor_factory=DictCursor
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
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    is_admin INTEGER DEFAULT 0,
                    daily_target INTEGER DEFAULT 3,
                    email VARCHAR(255),
                    phone VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Add email and phone columns dynamically if they do not exist
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255)")
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(50)")
            
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
                    id SERIAL PRIMARY KEY,
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

init_db()

# -------------------------------------------------------------
# Route Guards
# -------------------------------------------------------------
def get_current_user():
    if 'user_id' in session:
        return {'id': session['user_id'], 'username': session['username'], 'is_admin': session['is_admin']}
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
    
    import requests
    
    # 1. Try Resend HTTP API
    if resend_api_key:
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
            
    # 2. Try SendGrid HTTP API
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
            
    # 3. Try Mailgun HTTP API
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
        print("[Email Warning] No email API provider keys (RESEND_API_KEY, SENDGRID_API_KEY, MAILGUN_API_KEY) configured. Falling back to console.", flush=True)
            
    # Fallback console log for local development
    print(f"\n[VERIFICATION CODE FALLBACK] Sent code '{code}' to '{target}' for '{purpose}'\n", flush=True)
    return False

@app.route('/api/auth/send-code', methods=['POST'])
def send_code():
    data = request.json or {}
    username = (data.get('username') or '').strip()
    target = (data.get('target') or '').strip()
    purpose = data.get('purpose')
    
    if not target or purpose not in ('signup', 'reset'):
        return jsonify({'error': 'Target and valid purpose are required.'}), 400
        
    db = get_db()
    cursor = db.cursor()
    
    if purpose == 'signup':
        if not username:
            return jsonify({'error': 'Username is required.'}), 400
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
        "INSERT INTO verification_codes (target, code, purpose) VALUES (%s, %s, %s)",
        (target, code, purpose)
    )
    db.commit()
    
    # Try sending via real service, fallback to console log
    sent_real = send_otp_message(target, code, purpose)
    
    return jsonify({
        'message': 'Verification code sent successfully.',
        'sent_real': sent_real
    })

@app.route('/api/auth/signup', methods=['POST'])
def signup():
    data = request.json or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    email = (data.get('email') or '').strip()
    code = (data.get('code') or '').strip()
    
    if len(username) < 3 or len(password) < 6:
        return jsonify({'error': 'Username must be at least 3 chars; password at least 6 chars.'}), 400
        
    if not email:
        return jsonify({'error': 'Email is required.'}), 400
        
    if not code:
        return jsonify({'error': 'Verification code is required.'}), 400
        
    db = get_db()
    cursor = db.cursor()
    
    # Check verification code matches
    cursor.execute(
        "SELECT code FROM verification_codes WHERE target = %s AND purpose = 'signup' ORDER BY id DESC LIMIT 1",
        (email,)
    )
    row = cursor.fetchone()
    
    if not row or row['code'] != code:
        return jsonify({'error': 'Wrong verification code.'}), 400
        
    try:
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cursor.execute(
            "INSERT INTO users (username, password_hash, email, phone) VALUES (%s, %s, %s, %s)",
            (username, hashed, email, '')
        )
        
        # Delete verification codes for this target
        cursor.execute("DELETE FROM verification_codes WHERE target = %s", (email,))
        db.commit()
        
        # Log user in directly
        cursor.execute("SELECT id, username, is_admin FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['is_admin'] = user['is_admin']
        
        return jsonify({
            'message': 'Signup successful',
            'user': {'username': user['username'], 'is_admin': bool(user['is_admin'])}
        }), 201
    except psycopg2.IntegrityError:
        return jsonify({'error': 'Username is already taken.'}), 400

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    
    if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['is_admin'] = user['is_admin']
        
        return jsonify({
            'message': 'Login successful',
            'user': {'username': user['username'], 'is_admin': bool(user['is_admin'])}
        })
    return jsonify({'error': 'Invalid username or password.'}), 401

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'})

@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    user = get_current_user()
    if user:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT daily_target FROM users WHERE id = %s", (user['id'],))
        row = cursor.fetchone()
        
        return jsonify({
            'authenticated': True,
            'user': {
                'username': user['username'],
                'is_admin': bool(user['is_admin']),
                'daily_target': row['daily_target']
            }
        })
    return jsonify({'authenticated': False})

@app.route('/api/auth/reset-password', methods=['POST'])
def reset_password():
    data = request.json or {}
    username = (data.get('username') or '').strip()
    verification = (data.get('verification') or '').strip()
    new_password = data.get('new_password') or ''
    code = (data.get('code') or '').strip()
    
    if not username or not verification or not code or len(new_password) < 6:
        return jsonify({'error': 'Username, verification, code, and a valid new password are required.'}), 400
        
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
        "SELECT code FROM verification_codes WHERE target = %s AND purpose = 'reset' ORDER BY id DESC LIMIT 1",
        (verification,)
    )
    code_row = cursor.fetchone()
    if not code_row or code_row['code'] != code:
        return jsonify({'error': 'Wrong verification code.'}), 400
        
    hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (hashed, row['id']))
    cursor.execute("DELETE FROM verification_codes WHERE target = %s", (verification,))
    db.commit()
    
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
    
    if not username or daily_target is None:
        return jsonify({'error': 'Username and Daily Target are required.'}), 400
        
    db = get_db()
    cursor = db.cursor()
    
    try:
        cursor.execute(
            "UPDATE users SET username = %s, daily_target = %s WHERE id = %s",
            (username, int(daily_target), user['id'])
        )
        db.commit()
        session['username'] = username
        return jsonify({'message': 'Settings updated successfully'})
    except psycopg2.IntegrityError:
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
    cursor.execute("SELECT * FROM problems WHERE user_id = %s", (user['id'],))
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
    name = (data.get('name') or '').strip()
    difficulty = data.get('difficulty')
    platform = (data.get('platform') or '').strip()
    topic = (data.get('topic') or '').strip()
    date = data.get('date')
    url = (data.get('url') or '').strip()
    notes = (data.get('notes') or '').strip()
    associated_plans = data.get('plans') or [] # List of plan IDs
    
    if not name or not difficulty or not platform or not topic or not date:
        return jsonify({'error': 'Missing required problem fields.'}), 400
        
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
            SET name = %s, difficulty = %s, platform = %s, topic = %s, date = %s, url = %s, notes = %s
            WHERE id = %s AND user_id = %s
        ''', (name, difficulty, platform, topic, date, url, notes, pid, user['id']))
    else:
        # Create new
        pid = f"prob-{int(bcrypt.gensalt()[4:12].hex(), 16)}" # Generate secure key
        cursor.execute('''
            INSERT INTO problems (id, user_id, name, difficulty, platform, topic, date, url, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (pid, user['id'], name, difficulty, platform, topic, date, url, notes))
        
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
    if not cursor.fetchone():
        return jsonify({'error': 'Problem log not found or unauthorized.'}), 404
        
    cursor.execute("DELETE FROM problems WHERE id = %s", (pid,))
    db.commit()
    return jsonify({'message': 'Problem log deleted successfully'})

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
    
    # Validate all IDs belong to the user
    placeholders = ','.join('%s' for _ in ids)
    cursor.execute(
        f"SELECT id FROM problems WHERE id IN ({placeholders}) AND user_id = %s",
        (*ids, user['id'])
    )
    valid_ids = [row['id'] for row in cursor.fetchall()]
    
    if not valid_ids:
        return jsonify({'error': 'No valid owned problems to delete'}), 400
        
    valid_placeholders = ','.join('%s' for _ in valid_ids)
    cursor.execute(f"DELETE FROM problems WHERE id IN ({valid_placeholders})", valid_ids)
    db.commit()
    
    return jsonify({'message': f'Successfully deleted {len(valid_ids)} problem logs.'})

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
    cursor.execute("SELECT * FROM plans WHERE user_id = %s", (user['id'],))
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
    title = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip()
    target_count = data.get('targetCount')
    color = data.get('color')
    
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
    if not cursor.fetchone():
        return jsonify({'error': 'Study plan not found or unauthorized.'}), 404
        
    cursor.execute("DELETE FROM plans WHERE id = %s", (plan_id,))
    db.commit()
    return jsonify({'message': 'Study plan deleted successfully'})

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
    
    if scope == "problems":
        cursor.execute("DELETE FROM problems WHERE user_id = %s", (user['id'],))
        db.commit()
        return jsonify({'message': 'All problem logs cleared successfully.'})
    elif scope == "plans":
        cursor.execute("DELETE FROM plans WHERE user_id = %s", (user['id'],))
        db.commit()
        return jsonify({'message': 'All customized study plans deleted successfully.'})
    elif scope == "all":
        cursor.execute("DELETE FROM problems WHERE user_id = %s", (user['id'],))
        cursor.execute("DELETE FROM plans WHERE user_id = %s", (user['id'],))
        cursor.execute("UPDATE users SET username = %s, daily_target = 3 WHERE id = %s", (user['username'], user['id']))
        db.commit()
        return jsonify({'message': 'Entire application data reset successfully.'})
        
    return jsonify({'error': 'Invalid reset scope'}), 400

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
    
    # 2. Total solved problems
    cursor.execute("SELECT COUNT(*) as count FROM problems")
    total_problems = cursor.fetchone()['count']
    
    # 3. User lists with registration date and solve totals
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
