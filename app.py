import os, uuid, sqlite3
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-me-before-production')

DB = os.environ.get('DB_PATH', 'shop.db')
UPLOAD_DIR = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

SHOP_NAME = os.environ.get('SHOP_NAME', 'FF DIAMOND TOP-UP CENTER')
UPI_ID = os.environ.get('UPI_ID', 'yourupi@upi')
ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'change-this-password')

PACKAGES = [
    {'id': 1, 'diamonds': 310, 'price': 60, 'old': 120, 'badge': 'POPULAR'},
    {'id': 2, 'diamonds': 520, 'price': 100, 'old': 200, 'badge': ''},
    {'id': 3, 'diamonds': 1060, 'price': 200, 'old': 400, 'badge': 'BEST VALUE'},
    {'id': 4, 'diamonds': 2180, 'price': 400, 'old': 800, 'badge': ''},
    {'id': 5, 'diamonds': 5600, 'price': 800, 'old': 1600, 'badge': ''},
]

ALLOWED_EXT = {'.jpg', '.jpeg', '.png', '.webp'}
MAX_UPLOAD = 5 * 1024 * 1024


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db()
    con.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_code TEXT UNIQUE NOT NULL,
        uid TEXT NOT NULL,
        server TEXT NOT NULL,
        diamonds INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        payment_status TEXT NOT NULL DEFAULT 'pending',
        screenshot TEXT,
        utr TEXT
    )''')
    con.commit(); con.close()


def get_package(pid):
    return next((p for p in PACKAGES if p['id'] == pid), None)


def admin_required():
    if not session.get('admin'):
        abort(403)


@app.route('/')
def home():
    return render_template('index.html', packages=PACKAGES, shop_name=SHOP_NAME)


@app.route('/buy/<int:package_id>', methods=['GET', 'POST'])
def buy(package_id):
    package = get_package(package_id)
    if not package: abort(404)
    if request.method == 'POST':
        uid = request.form.get('uid', '').strip()
        server = request.form.get('server', '').strip()
        if not uid or not server or len(uid) > 40 or len(server) > 40:
            flash('UID aur server sahi tarah bharein.')
            return redirect(url_for('buy', package_id=package_id))
        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=10)
        code = 'FF' + uuid.uuid4().hex[:10].upper()
        con = db()
        con.execute('''INSERT INTO orders
            (order_code, uid, server, diamonds, amount, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (code, uid, server, package['diamonds'], package['price'], now.isoformat(), expires.isoformat()))
        con.commit()
        oid = con.execute('SELECT last_insert_rowid()').fetchone()[0]
        con.close()
        return redirect(url_for('payment', order_id=oid))
    return render_template('buy.html', package=package)


@app.route('/payment/<int:order_id>')
def payment(order_id):
    con = db(); order = con.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone(); con.close()
    if not order: abort(404)
    return render_template('payment.html', order=order, upi_id=UPI_ID)


@app.route('/submit-payment/<int:order_id>', methods=['POST'])
def submit_payment(order_id):
    con = db(); order = con.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()
    if not order:
        con.close(); abort(404)
    expires = datetime.fromisoformat(order['expires_at'])
    if datetime.now(timezone.utc) >= expires:
        con.close(); flash('Payment window expire ho gaya. New order banayein.')
        return redirect(url_for('payment', order_id=order_id))
    utr = request.form.get('utr', '').strip()
    file = request.files.get('screenshot')
    if not utr or len(utr) > 100 or not file or not file.filename:
        con.close(); flash('Payment screenshot aur UTR/reference number submit karein.')
        return redirect(url_for('payment', order_id=order_id))
    ext = os.path.splitext(secure_filename(file.filename))[1].lower()
    if ext not in ALLOWED_EXT or (request.content_length and request.content_length > MAX_UPLOAD):
        con.close(); flash('Valid JPG/PNG/WEBP screenshot (max 5MB) upload karein.')
        return redirect(url_for('payment', order_id=order_id))
    filename = f"{order['order_code']}_{uuid.uuid4().hex[:8]}{ext}"
    file.save(os.path.join(UPLOAD_DIR, filename))
    con.execute("UPDATE orders SET screenshot=?, utr=?, payment_status='review' WHERE id=?", (filename, utr, order_id))
    con.commit(); con.close()
    return render_template('success.html', order=order)


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USER and request.form.get('password') == ADMIN_PASS:
            session.clear(); session['admin'] = True
            return redirect(url_for('admin'))
        flash('Wrong admin login.')
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    session.clear(); return redirect(url_for('admin_login'))


@app.route('/admin')
def admin():
    admin_required()
    con = db(); orders = con.execute('SELECT * FROM orders ORDER BY id DESC').fetchall(); con.close()
    return render_template('admin.html', orders=orders, shop_name=SHOP_NAME)


@app.route('/admin/order/<int:order_id>/<action>', methods=['POST'])
def admin_action(order_id, action):
    admin_required()
    if action not in ('approved', 'rejected'): abort(400)
    con = db(); con.execute('UPDATE orders SET payment_status=? WHERE id=?', (action, order_id)); con.commit(); con.close()
    return redirect(url_for('admin'))


init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
