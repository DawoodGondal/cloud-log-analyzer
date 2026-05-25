import os
import multiprocessing
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from mapreduce import run_mapreduce
from database import init_db, register_user, get_user, save_result, log_event, get_history

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret')

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'log', 'txt'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

if multiprocessing.current_process().name == 'MainProcess':
    try:
        init_db()
    except Exception as e:
        print(f"DB init warning: {e}")

# ── Auth ──────────────────────────────────────────────────────────────────────

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username):
        self.id = str(id)
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    row = None
    import psycopg2
    try:
        from database import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('SELECT id, username FROM users WHERE id = %s', (user_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
    except:
        pass
    if row:
        return User(row[0], row[1])
    return None

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        row = get_user(username)
        if row and check_password_hash(row[2], password):
            user = User(row[0], row[1])
            login_user(user)
            log_event('LOGIN_SUCCESS', username=username)
            return redirect(url_for('dashboard'))
        log_event('LOGIN_FAILED', username=username)
        flash('Invalid username or password.')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm', '')

        if len(username) < 3:
            flash('Username must be at least 3 characters.')
        elif len(password) < 6:
            flash('Password must be at least 6 characters.')
        elif password != confirm:
            flash('Passwords do not match.')
        else:
            hashed = generate_password_hash(password)
            user_id = register_user(username, hashed)
            if user_id is None:
                flash('Username already taken. Choose another.')
            else:
                log_event('REGISTER', username=username)
                flash('Account created! Please log in.')
                return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    log_event('LOGOUT', username=current_user.username)
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    history = get_history()
    return render_template('dashboard.html', history=history)

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    if 'logfile' not in request.files:
        flash('No file selected.')
        return redirect(url_for('dashboard'))

    file = request.files['logfile']
    if file.filename == '':
        flash('No file selected.')
        return redirect(url_for('dashboard'))

    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        flash('Only .log or .txt files allowed.')
        return redirect(url_for('dashboard'))

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    result = run_mapreduce(filepath)
    save_result(filename, result['errors'], result['traffic'])
    log_event('FILE_ANALYZED', username=current_user.username, detail=filename)

    return render_template('results.html',
                           filename=filename,
                           errors=result['errors'],
                           traffic=result['traffic'])

if __name__ == '__main__':
    app.run(debug=True)