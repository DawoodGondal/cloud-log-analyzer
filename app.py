import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from mapreduce import run_mapreduce
from database import init_db, save_result, log_event, get_history

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret')

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'log', 'txt'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize DB tables on startup
init_db()

# ── Auth ──────────────────────────────────────────────────────────────────────

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class AdminUser(UserMixin):
    def __init__(self):
        self.id = 'admin'
        self.username = os.getenv('ADMIN_USERNAME', 'admin')

admin = AdminUser()

@login_manager.user_loader
def load_user(user_id):
    if user_id == 'admin':
        return admin
    return None

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if (username == os.getenv('ADMIN_USERNAME', 'admin') and
                password == os.getenv('ADMIN_PASSWORD', 'admin123')):
            login_user(admin)
            log_event('LOGIN_SUCCESS', username=username)
            return redirect(url_for('dashboard'))
        log_event('LOGIN_FAILED', username=username, detail='Bad credentials')
        flash('Invalid credentials. Try again.')
    return render_template('login.html')

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

    # Run MapReduce
    result = run_mapreduce(filepath)

    # Save to database + audit trail
    save_result(filename, result['errors'], result['traffic'])
    log_event('FILE_ANALYZED', username=current_user.username, detail=filename)

    return render_template('results.html',
                           filename=filename,
                           errors=result['errors'],
                           traffic=result['traffic'])

if __name__ == '__main__':
    app.run(debug=True)