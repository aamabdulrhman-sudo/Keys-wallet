import os
import sys
import sqlite3
import platform
from flask import Flask, render_template, redirect, url_for, flash, request, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'secret_key_for_session'

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

DB_PATH = 'vault.db'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            site_name TEXT NOT NULL,
            url TEXT,
            username_field TEXT,
            password_field TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS shared_credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            credential_id INTEGER NOT NULL,
            shared_with_user_id INTEGER NOT NULL,
            shared_by_user_id INTEGER NOT NULL,
            FOREIGN KEY (credential_id) REFERENCES credentials (id),
            FOREIGN KEY (shared_with_user_id) REFERENCES users (id),
            FOREIGN KEY (shared_by_user_id) REFERENCES users (id)
        )''')
        conn.commit()

def is_installed():
    with get_db_connection() as conn:
        count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    return count > 0

def check_system_requirements():
    checks = []
    checks.append({'name': 'Python', 'status': True, 'version': platform.python_version()})
    try:
        import flask
        checks.append({'name': 'Flask', 'status': True, 'version': flask.__version__})
    except ImportError:
        checks.append({'name': 'Flask', 'status': False, 'version': 'غير مثبت'})
    try:
        import flask_login
        checks.append({'name': 'Flask-Login', 'status': True, 'version': flask_login.__version__})
    except ImportError:
        checks.append({'name': 'Flask-Login', 'status': False, 'version': 'غير مثبت'})
    try:
        import werkzeug
        checks.append({'name': 'Werkzeug', 'status': True, 'version': werkzeug.__version__})
    except ImportError:
        checks.append({'name': 'Werkzeug', 'status': False, 'version': 'غير مثبت'})
    db_ok = os.access(os.path.dirname(os.path.abspath(DB_PATH)) or '.', os.W_OK)
    checks.append({'name': 'SQLite', 'status': True, 'version': sqlite3.sqlite_version})
    checks.append({'name': 'صلاحيات الكتابة', 'status': db_ok, 'version': 'مجلد العمل'})
    all_ok = all(c['status'] for c in checks)
    return checks, all_ok

class User(UserMixin):
    def __init__(self, id, username, is_admin):
        self.id = id
        self.username = username
        self.is_admin = is_admin

@login_manager.user_loader
def load_user(user_id):
    with get_db_connection() as conn:
        user_data = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if user_data:
            return User(user_data['id'], user_data['username'], user_data['is_admin'])
    return None

@app.before_request
def check_setup_wizard():
    skip_endpoints = ['setup_wizard', 'login', 'register', 'static', 'index']
    if request.endpoint in skip_endpoints or not request.endpoint:
        return
    if not is_installed():
        return redirect(url_for('setup_wizard'))

@app.route('/setup')
@app.route('/setup/<int:step>')
def setup_wizard(step=1):
    if is_installed() and step == 1:
        return redirect(url_for('login'))
    if step < 1 or step > 4:
        return redirect(url_for('setup_wizard', step=1))

    if step == 1:
        return render_template('setup.html', step=1)

    if step == 2:
        checks, all_ok = check_system_requirements()
        return render_template('setup.html', step=2, checks=checks, all_ok=all_ok)

    if step == 3:
        if is_installed():
            return redirect(url_for('login'))
        return render_template('setup.html', step=3)

    if step == 4:
        return render_template('setup.html', step=4)

    return render_template('setup.html', step=1)

@app.route('/setup/create_admin', methods=['POST'])
def setup_create_admin():
    if is_installed():
        return redirect(url_for('login'))
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    confirm = request.form.get('confirm_password', '').strip()

    if not username or not password:
        flash('يرجى ملء جميع الحقول!', 'danger')
        return redirect(url_for('setup_wizard', step=3))

    if len(username) < 3:
        flash('اسم المدير يجب أن يكون 3 أحرف على الأقل!', 'danger')
        return redirect(url_for('setup_wizard', step=3))

    if len(password) < 6:
        flash('كلمة المرور يجب أن تكون 6 أحرف على الأقل!', 'danger')
        return redirect(url_for('setup_wizard', step=3))

    if password != confirm:
        flash('كلمتا المرور غير متطابقتين!', 'danger')
        return redirect(url_for('setup_wizard', step=3))

    try:
        with get_db_connection() as conn:
            conn.execute('INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)',
                         (username, generate_password_hash(password), 1))
            conn.commit()
        session['installer_completed'] = True
        flash(f'تم إنشاء حساب المدير "{username}" بنجاح!', 'success')
        return redirect(url_for('setup_wizard', step=4))
    except sqlite3.IntegrityError:
        flash('اسم المستخدم مستخدم بالفعل!', 'danger')
        return redirect(url_for('setup_wizard', step=3))

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        try:
            with get_db_connection() as conn:
                conn.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)',
                             (username, generate_password_hash(password)))
                conn.commit()
            flash('تم التسجيل بنجاح! سجّل الدخول الآن.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('اسم المستخدم مستخدم بالفعل!', 'danger')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        with get_db_connection() as conn:
            user_data = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
            if user_data and check_password_hash(user_data['password_hash'], password):
                user = User(user_data['id'], user_data['username'], user_data['is_admin'])
                login_user(user)
                return redirect(url_for('dashboard'))
            flash('بيانات الدخول غير صحيحة!', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    my_creds = conn.execute('SELECT * FROM credentials WHERE user_id = ?', (current_user.id,)).fetchall()
    shared_with_me = conn.execute('''
        SELECT c.*, u.username as owner_name, sc.id as share_id
        FROM credentials c
        JOIN shared_credentials sc ON c.id = sc.credential_id
        JOIN users u ON sc.shared_by_user_id = u.id
        WHERE sc.shared_with_user_id = ?
    ''', (current_user.id,)).fetchall()
    users_list = conn.execute('SELECT id, username FROM users WHERE id != ?', (current_user.id,)).fetchall()
    conn.close()
    return render_template('dashboard.html', credentials=my_creds, shared_with_me=shared_with_me, users=users_list)

@app.route('/add_credential', methods=['POST'])
@login_required
def add_credential():
    site = request.form.get('site_name')
    url_val = request.form.get('url')
    user_f = request.form.get('username_field')
    pass_f = request.form.get('password_field')
    with get_db_connection() as conn:
        conn.execute('INSERT INTO credentials (user_id, site_name, url, username_field, password_field) VALUES (?, ?, ?, ?, ?)',
                     (current_user.id, site, url_val, user_f, pass_f))
        conn.commit()
    flash('تم حفظ الاعتماد بنجاح!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/delete_credential/<int:id>', methods=['POST'])
@login_required
def delete_credential(id):
    with get_db_connection() as conn:
        conn.execute('DELETE FROM shared_credentials WHERE credential_id = ?', (id,))
        conn.execute('DELETE FROM credentials WHERE id = ? AND user_id = ?', (id, current_user.id))
        conn.commit()
    flash('تم حذف الاعتماد!', 'warning')
    return redirect(url_for('dashboard'))

@app.route('/share_credential/<int:credential_id>', methods=['POST'])
@login_required
def share_credential(credential_id):
    target_user = request.form.get('user_id')
    if target_user:
        with get_db_connection() as conn:
            is_owner = conn.execute('SELECT 1 FROM credentials WHERE id = ? AND user_id = ?', (credential_id, current_user.id)).fetchone()
            if is_owner:
                existing = conn.execute('SELECT 1 FROM shared_credentials WHERE credential_id = ? AND shared_with_user_id = ?', (credential_id, target_user)).fetchone()
                if not existing:
                    conn.execute('INSERT INTO shared_credentials (credential_id, shared_with_user_id, shared_by_user_id) VALUES (?, ?, ?)',
                                 (credential_id, target_user, current_user.id))
                    conn.commit()
                    flash('تمت مشاركة الاعتماد بنجاح!', 'success')
                else:
                    flash('هذا الاعتماد مشترك مع هذا المستخدم بالفعل!', 'info')
            else:
                flash('ليس لديك صلاحية مشاركة هذا الاعتماد!', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/unshare_credential/<int:share_id>', methods=['POST'])
@login_required
def unshare_credential(share_id):
    with get_db_connection() as conn:
        conn.execute('DELETE FROM shared_credentials WHERE id = ? AND shared_by_user_id = ?', (share_id, current_user.id))
        conn.commit()
    flash('تم إلغاء المشاركة!', 'warning')
    return redirect(url_for('dashboard'))

@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin:
        flash('ليس لديك صلاحية الوصول!', 'danger')
        return redirect(url_for('dashboard'))
    with get_db_connection() as conn:
        users = conn.execute('SELECT id, username, is_admin FROM users ORDER BY is_admin DESC, id ASC').fetchall()
        stats = {
            'total_users': conn.execute('SELECT COUNT(*) FROM users').fetchone()[0],
            'total_credentials': conn.execute('SELECT COUNT(*) FROM credentials').fetchone()[0],
            'total_shares': conn.execute('SELECT COUNT(*) FROM shared_credentials').fetchone()[0],
            'admin_count': conn.execute('SELECT COUNT(*) FROM users WHERE is_admin = 1').fetchone()[0],
        }
    return render_template('admin_users.html', users=users, stats=stats)

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if not current_user.is_admin:
        flash('ليس لديك صلاحية!', 'danger')
        return redirect(url_for('dashboard'))
    if user_id == current_user.id:
        flash('لا يمكنك حذف حسابك الخاص!', 'danger')
        return redirect(url_for('admin_users'))
    with get_db_connection() as conn:
        user = conn.execute('SELECT is_admin FROM users WHERE id = ?', (user_id,)).fetchone()
        if user and user['is_admin']:
            admin_count = conn.execute('SELECT COUNT(*) FROM users WHERE is_admin = 1').fetchone()[0]
            if admin_count <= 1:
                flash('لا يمكن حذف آخر مدير في النظام!', 'danger')
                return redirect(url_for('admin_users'))
        conn.execute('DELETE FROM shared_credentials WHERE shared_with_user_id = ? OR shared_by_user_id = ?', (user_id, user_id))
        conn.execute('DELETE FROM credentials WHERE user_id = ?', (user_id,))
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
    flash('تم حذف المستخدم وبياناته بنجاح!', 'warning')
    return redirect(url_for('admin_users'))

@app.route('/admin/toggle_admin/<int:user_id>', methods=['POST'])
@login_required
def admin_toggle_admin(user_id):
    if not current_user.is_admin:
        flash('ليس لديك صلاحية!', 'danger')
        return redirect(url_for('dashboard'))
    if user_id == current_user.id:
        flash('لا يمكنك تغيير صلاحياتك!', 'danger')
        return redirect(url_for('admin_users'))
    with get_db_connection() as conn:
        user = conn.execute('SELECT is_admin FROM users WHERE id = ?', (user_id,)).fetchone()
        if user:
            new_status = 0 if user['is_admin'] else 1
            if new_status == 0:
                admin_count = conn.execute('SELECT COUNT(*) FROM users WHERE is_admin = 1').fetchone()[0]
                if admin_count <= 1:
                    flash('لا يمكن إزالة صلاحية آخر مدير!', 'danger')
                    return redirect(url_for('admin_users'))
            conn.execute('UPDATE users SET is_admin = ? WHERE id = ?', (new_status, user_id))
            conn.commit()
            if new_status:
                flash('تم ترقية المستخدم إلى مدير!', 'success')
            else:
                flash('تم إزالة صلاحيات الإداري!', 'warning')
    return redirect(url_for('admin_users'))

@app.route('/admin/add_user', methods=['POST'])
@login_required
def admin_add_user():
    if not current_user.is_admin:
        flash('ليس لديك صلاحية!', 'danger')
        return redirect(url_for('dashboard'))
    username = request.form.get('username')
    password = request.form.get('password')
    is_admin = 1 if request.form.get('is_admin') else 0
    if username and password:
        try:
            with get_db_connection() as conn:
                conn.execute('INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)',
                             (username, generate_password_hash(password), is_admin))
                conn.commit()
            flash(f'تم إنشاء حساب "{username}" بنجاح!', 'success')
        except sqlite3.IntegrityError:
            flash('اسم المستخدم مستخدم بالفعل!', 'danger')
    else:
        flash('يرجى إدخال جميع البيانات!', 'danger')
    return redirect(url_for('admin_users'))

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
