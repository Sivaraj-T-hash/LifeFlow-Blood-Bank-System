import smtplib
from email.message import EmailMessage
import sqlite3
import csv
import os
import math
import random
from io import StringIO
from datetime import date, datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = 'super_secret_key_bloodbank'

# --- CONFIGURATION FOR UPLOADS ---
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- SHARED DATA ---
HOSPITALS_DATA = [
    {"name": "Rajiv Gandhi Govt General Hospital", "lat": 13.0815, "lng": 80.2768, "type": "Govt", "email": "rajiv@gov.in"},
    {"name": "Apollo Hospitals (Greams Road)", "lat": 13.0630, "lng": 80.2555, "type": "Private", "email": "apollo@private.com"},
    {"name": "Government Stanley Hospital", "lat": 13.1067, "lng": 80.2882, "type": "Govt", "email": "stanley@gov.in"},
    {"name": "MIOT International", "lat": 13.0298, "lng": 80.1866, "type": "Private", "email": "miot@private.com"},
    {"name": "Rotary Central Blood Bank", "lat": 13.0587, "lng": 80.2642, "type": "NGO", "email": "rotary@ngo.org"}
]

# =========================================================================
# DBMS FEATURE: CUSTOM SCALAR FUNCTION FOR SPATIAL QUERIES
# =========================================================================
def haversine(lat1, lon1, lat2, lon2):
    """Calculates the distance between two points on the earth using spherical trigonometry"""
    try:
        if None in (lat1, lon1, lat2, lon2) or "" in (lat1, lon1, lat2, lon2): return 9999.0
        lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
        R = 6371.0 # Radius of Earth in km
        dLat = math.radians(lat2 - lat1)
        dLon = math.radians(lon2 - lon1)
        a = math.sin(dLat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        return R * c
    except:
        return 9999.0

def get_db_connection():
    conn = sqlite3.connect('bloodbank.db')
    conn.row_factory = sqlite3.Row
    # Inject our Python math function directly into the SQLite database engine!
    conn.create_function("haversine", 4, haversine) 
    return conn

def init_db():
    conn = sqlite3.connect('bloodbank.db')
    c = conn.cursor()
    
    # 1. Existing Tables
    c.execute('''CREATE TABLE IF NOT EXISTS donors 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, age INTEGER, weight REAL, 
                  blood_group TEXT, city TEXT, address TEXT, phone TEXT UNIQUE, password TEXT, role TEXT DEFAULT 'user')''')
    c.execute('''CREATE TABLE IF NOT EXISTS hospitals
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT UNIQUE, password TEXT, lat REAL, lng REAL, type TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS appointments
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, donor_id INTEGER, hospital_id INTEGER, 
                  date TEXT, time_slot TEXT, status TEXT DEFAULT 'Scheduled',
                  FOREIGN KEY(donor_id) REFERENCES donors(id), FOREIGN KEY(hospital_id) REFERENCES hospitals(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS donations
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, donor_id INTEGER, date TEXT, volume_ml INTEGER, hospital TEXT, status TEXT DEFAULT 'Pending')''')
    
    try: c.execute("SELECT status FROM donations LIMIT 1")
    except sqlite3.OperationalError: c.execute("ALTER TABLE donations ADD COLUMN status TEXT DEFAULT 'Approved'") 

    c.execute('''CREATE TABLE IF NOT EXISTS camp_hosts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, organization_name TEXT, leader_name TEXT, 
                  email TEXT UNIQUE, phone TEXT, aadhar_number TEXT UNIQUE, password TEXT, city TEXT, address TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS camps
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, host_id INTEGER, name TEXT, 
                  date TEXT, time TEXT, location_name TEXT, lat REAL, lng REAL, 
                  estimated_participants INTEGER, city TEXT, status TEXT DEFAULT 'Upcoming',
                  FOREIGN KEY(host_id) REFERENCES camp_hosts(id))''')
    
    try: c.execute("ALTER TABLE camps ADD COLUMN photo_filename TEXT")
    except sqlite3.OperationalError: pass 

    c.execute('''CREATE TABLE IF NOT EXISTS camp_registrations
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, camp_id INTEGER, donor_id INTEGER, 
                  booking_date TEXT, status TEXT DEFAULT 'Registered',
                  FOREIGN KEY(camp_id) REFERENCES camps(id),
                  FOREIGN KEY(donor_id) REFERENCES donors(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS camp_photos
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, camp_id INTEGER, filename TEXT,
                  FOREIGN KEY(camp_id) REFERENCES camps(id))''')

    # =========================================================================
    # NEW FEATURE: EXTERNAL HOSPITAL STOCK TRACKER (For Map)
    # =========================================================================
    c.execute('''CREATE TABLE IF NOT EXISTS hospital_stock 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, hospital_id INTEGER, blood_group TEXT, units INTEGER,
                  UNIQUE(hospital_id, blood_group))''')

    # =========================================================================
    # DBMS FEATURE 1: B-TREE INDEXING FOR PERFORMANCE OPTIMIZATION
    # =========================================================================
    c.execute("CREATE INDEX IF NOT EXISTS idx_donor_bg ON donors(blood_group)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_donation_status ON donations(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_appointment_status ON appointments(status)")

    # =========================================================================
    # DBMS FEATURE 2: DATABASE TRIGGERS FOR SECURITY AUDITING
    # =========================================================================
    c.execute('''CREATE TABLE IF NOT EXISTS security_audit_log
                 (log_id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  table_name TEXT, 
                  action_type TEXT, 
                  record_id INTEGER, 
                  old_status TEXT, 
                  new_status TEXT, 
                  action_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

    c.execute('''CREATE TRIGGER IF NOT EXISTS audit_donation_update 
                 AFTER UPDATE OF status ON donations 
                 BEGIN 
                     INSERT INTO security_audit_log (table_name, action_type, record_id, old_status, new_status) 
                     VALUES ('donations', 'STATUS_UPDATE', NEW.id, OLD.status, NEW.status); 
                 END;''')
    
    c.execute('''CREATE TRIGGER IF NOT EXISTS audit_appointment_update 
                 AFTER UPDATE OF status ON appointments 
                 BEGIN 
                     INSERT INTO security_audit_log (table_name, action_type, record_id, old_status, new_status) 
                     VALUES ('appointments', 'STATUS_UPDATE', NEW.id, OLD.status, NEW.status); 
                 END;''')

    # =========================================================================
    # DBMS FEATURE 3: ADD GPS TO DONORS FOR SPATIAL ALGORITHM
    # =========================================================================
    try: c.execute("ALTER TABLE donors ADD COLUMN lat REAL")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE donors ADD COLUMN lng REAL")
    except sqlite3.OperationalError: pass
    
    donors_without_gps = c.execute("SELECT id FROM donors WHERE lat IS NULL").fetchall()
    for d in donors_without_gps:
        c.execute("UPDATE donors SET lat = ?, lng = ? WHERE id = ?", 
                 (13.08 + random.uniform(-0.1, 0.1), 80.27 + random.uniform(-0.1, 0.1), d[0]))

    # Seed Admin & Hospitals
    c.execute("SELECT * FROM donors WHERE role='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO donors (name, phone, email, password, role, blood_group) VALUES (?, ?, ?, ?, ?, ?)",
                  ('Super Admin', 'admin', 'admin@bloodbank.com', generate_password_hash('admin123'), 'admin', 'O+'))
    
    hashed_hosp_pw = generate_password_hash('password123')
    for h in HOSPITALS_DATA:
        c.execute("SELECT * FROM hospitals WHERE email=?", (h['email'],))
        if not c.fetchone():
            c.execute("INSERT INTO hospitals (name, email, password, lat, lng, type) VALUES (?, ?, ?, ?, ?, ?)",
                      (h['name'], h['email'], hashed_hosp_pw, h['lat'], h['lng'], h['type']))
    conn.commit()
    conn.close()

init_db()

# --- HELPER: CHECK ELIGIBILITY ---
def check_eligibility(user_id):
    conn = get_db_connection()
    last_manual = conn.execute("SELECT date FROM donations WHERE donor_id = ? AND (status = 'Approved' OR status = 'Pending' OR status = 'Archived') ORDER BY date DESC LIMIT 1", (user_id,)).fetchone()
    last_appt = conn.execute("SELECT date FROM appointments WHERE donor_id = ? AND status = 'Verified' ORDER BY date DESC LIMIT 1", (user_id,)).fetchone()
    conn.close()
    
    last_date = None
    if last_manual: last_date = datetime.strptime(last_manual['date'], '%Y-%m-%d').date()
    if last_appt:
        appt_date = datetime.strptime(last_appt['date'], '%Y-%m-%d').date()
        if not last_date or appt_date > last_date: last_date = appt_date
    
    if last_date:
        days_diff = (date.today() - last_date).days
        if days_diff < 90: return False, 90 - days_diff
    return True, 0

# --- HELPER: AUTOMATED EMAIL CONFIRMATION ---
def send_confirmation_email(recipient_email, donor_name, hospital_name, book_date, time_slot):
    try:
        SENDER_EMAIL = "life.flow.blood.donation.09@gmail.com" 
        APP_PASSWORD = "myqdidztbciuxpoh" 

        msg = EmailMessage()
        msg['Subject'] = f"LifeFlow: Appointment Confirmed - {hospital_name}"
        msg['From'] = SENDER_EMAIL
        msg['To'] = recipient_email
        
        content = f"""
Hi {donor_name},

Thank you for being a lifesaver! Your blood donation appointment has been successfully confirmed.

Here are your appointment details:
📅 Date: {book_date}
⏰ Time: {time_slot}
🏥 Hospital: {hospital_name}

Please try to arrive 10 minutes early and ensure you are well-hydrated. Your contribution brings hope and saves lives.

Warm regards,
The LifeFlow Team
        """
        msg.set_content(content)
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(SENDER_EMAIL, APP_PASSWORD)
            smtp.send_message(msg)
            
    except Exception as e:
        print(f"Email sending failed: {e}") 

@app.route('/')
def index():
    conn = get_db_connection()
    today_str = date.today().strftime('%Y-%m-%d')
    
    total_donors = conn.execute('SELECT COUNT(*) FROM donors WHERE role!="admin"').fetchone()[0]
    
    # Combined calculations for Total Units logic
    internal_units = conn.execute("SELECT COUNT(*) FROM appointments WHERE status='Verified'").fetchone()[0]
    external_units_row = conn.execute("SELECT SUM(units) FROM hospital_stock").fetchone()[0]
    external_units = external_units_row if external_units_row else 0
    total_verified = internal_units + external_units

    # Combined internal and external stock per blood group
    internal_stock = conn.execute("SELECT u.blood_group, COUNT(*) as count FROM donations d JOIN donors u ON d.donor_id = u.id WHERE d.status='Approved' GROUP BY u.blood_group").fetchall()
    external_stock = conn.execute("SELECT blood_group, SUM(units) as count FROM hospital_stock GROUP BY blood_group").fetchall()
    
    blood_stock = {g: 0 for g in ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']}
    
    # Tally up internal and external stock for the Home Page
    for row in internal_stock:
        if row['blood_group'] in blood_stock:
            blood_stock[row['blood_group']] += row['count']
    for row in external_stock:
        if row['blood_group'] in blood_stock:
            blood_stock[row['blood_group']] += row['count']
    
    leaderboard_data = conn.execute('''
        SELECT d.name, d.blood_group, SUM(dn.volume_ml) as total_volume
        FROM donors d
        JOIN donations dn ON d.id = dn.donor_id
        WHERE dn.status = 'Approved'
        GROUP BY d.id
        ORDER BY total_volume DESC, d.name ASC LIMIT 3
    ''').fetchall()

    upcoming_camps = conn.execute('''
        SELECT c.*, (SELECT COUNT(*) FROM camp_registrations cr WHERE cr.camp_id = c.id) as registered_count 
        FROM camps c WHERE c.status='Upcoming' AND c.date >= ? ORDER BY c.date ASC LIMIT 3
    ''', (today_str,)).fetchall()

    gallery_photos = conn.execute('''
        SELECT cp.filename, c.name, c.location_name, c.date 
        FROM camp_photos cp JOIN camps c ON cp.camp_id = c.id 
        ORDER BY c.date DESC, cp.id ASC LIMIT 10
    ''').fetchall()

    # =========================================================================
    # NEW FEATURE: HOSPITAL INVENTORY LIST FOR HOMEPAGE
    # =========================================================================
    hospitals_db = conn.execute('''
        SELECT h.id, h.name, h.type, h.email as contact, 
        (SELECT COUNT(*) FROM donations d WHERE d.hospital = h.name AND d.status = 'Approved') as internal_stock,
        IFNULL((SELECT SUM(units) FROM hospital_stock hs WHERE hs.hospital_id = h.id), 0) as external_stock
        FROM hospitals h
    ''').fetchall()
    
    hospital_list = []
    for h in hospitals_db:
        hd = dict(h)
        hd['total_stock'] = hd['internal_stock'] + hd['external_stock']
        hd['city'] = 'Chennai' # Since predefined ones are in Chennai, this enables the filter
        hospital_list.append(hd)

    conn.close()
    return render_template('index.html', total_donors=total_donors, total_units=total_verified, 
                           lives_saved=total_verified*3, blood_stock=blood_stock, 
                           upcoming_camps=upcoming_camps, gallery_photos=gallery_photos,
                           leaderboard=leaderboard_data, hospital_list=hospital_list)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_id = request.form['login_id']
        password = request.form['password']
        role_type = request.form.get('login_type') 
        conn = get_db_connection()
        if role_type == 'hospital':
            user = conn.execute('SELECT * FROM hospitals WHERE email = ?', (login_id,)).fetchone()
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']; session['role'] = 'hospital'; session['name'] = user['name']
                return redirect(url_for('hospital_dashboard'))
        elif role_type == 'host':
            user = conn.execute('SELECT * FROM camp_hosts WHERE email = ?', (login_id,)).fetchone()
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']; session['role'] = 'host'; session['name'] = user['organization_name']
                return redirect(url_for('host_dashboard'))
        else: 
            user = conn.execute('SELECT * FROM donors WHERE phone = ? OR email = ?', (login_id, login_id)).fetchone()
            if user and check_password_hash(user['password'], password):
                if user['role'] == 'admin': 
                    flash('Please use Admin Login', 'warning'); return redirect(url_for('admin_login'))
                session['user_id'] = user['id']; session['role'] = user['role']; session['name'] = user['name']
                return redirect(url_for('user_profile'))
        conn.close(); flash('Invalid Credentials', 'danger')
    return render_template('login.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM donors WHERE email = ? AND role = 'admin'", (request.form['email'],)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], request.form['password']):
            session['user_id'] = user['id']; session['role'] = 'admin'; session['name'] = user['name']
            return redirect(url_for('admin_dashboard'))
        flash('Invalid Admin Credentials', 'danger')
    return render_template('admin_login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            conn = get_db_connection()
            conn.execute("INSERT INTO donors (name, email, phone, password, blood_group, city, age, weight, address, role) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'user')",
                         (request.form['name'], request.form['email'], request.form['phone'], generate_password_hash(request.form['password']), request.form['blood_group'], request.form['city'], request.form['age'], request.form['weight'], request.form['address']))
            conn.commit(); conn.close(); return redirect(url_for('login'))
        except: flash('Phone already used.', 'danger')
    return render_template('register.html')

@app.route('/register_host', methods=['GET', 'POST'])
def register_host():
    if request.method == 'POST':
        try:
            conn = get_db_connection()
            conn.execute("INSERT INTO camp_hosts (organization_name, leader_name, email, phone, aadhar_number, password, city, address) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                         (request.form['organization_name'], request.form['leader_name'], request.form['email'], request.form['phone'], request.form['aadhar_number'], generate_password_hash(request.form['password']), request.form['city'], request.form['address']))
            conn.commit(); conn.close(); flash('Host Account Created!', 'success'); return redirect(url_for('login'))
        except: flash('Error creating host account.', 'danger')
    return render_template('register_host.html')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

@app.route('/host/dashboard', methods=['GET', 'POST'])
def host_dashboard():
    if session.get('role') != 'host': return redirect(url_for('login'))
    conn = get_db_connection()
    if request.method == 'POST':
        start_date = request.form['date']; end_date = request.form.get('end_date'); time_str = request.form['time']
        if end_date and end_date != start_date: time_str = f"{time_str} (Ends: {end_date})"
        conn.execute("INSERT INTO camps (host_id, name, date, time, location_name, lat, lng, estimated_participants, city) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (session['user_id'], request.form['camp_name'], start_date, time_str, request.form['location_name'], request.form['lat'], request.form['lng'], request.form['estimated_participants'], request.form['city']))
        conn.commit(); flash('Camp Scheduled!', 'success'); return redirect(url_for('host_dashboard'))
    
    my_camps = conn.execute("SELECT c.*, (SELECT COUNT(*) FROM camp_registrations cr JOIN donors d ON cr.donor_id = d.id WHERE cr.camp_id = c.id) as registered_count FROM camps c WHERE host_id = ? ORDER BY date DESC", (session['user_id'],)).fetchall()
    today_str = date.today().strftime('%Y-%m-%d')
    pending_uploads = conn.execute("SELECT * FROM camps c WHERE c.host_id = ? AND c.date < ? AND NOT EXISTS (SELECT 1 FROM camp_photos cp WHERE cp.camp_id = c.id)", (session['user_id'], today_str)).fetchall()
    host_details = conn.execute('SELECT * FROM camp_hosts WHERE id = ?', (session['user_id'],)).fetchone()
    
    camp_donors = conn.execute('''
        SELECT cr.camp_id, d.name, d.blood_group, d.phone, d.email, d.city 
        FROM camp_registrations cr 
        JOIN donors d ON cr.donor_id = d.id 
        JOIN camps c ON cr.camp_id = c.id 
        WHERE c.host_id = ?
    ''', (session['user_id'],)).fetchall()
    
    conn.close()
    return render_template('host_dashboard.html', camps=my_camps, host=host_details, camp_donors=camp_donors, pending_uploads=pending_uploads)

@app.route('/host/upload_photo', methods=['POST'])
def upload_camp_photo():
    if session.get('role') != 'host': return redirect(url_for('login'))
    camp_id = request.form['camp_id']
    files = request.files.getlist('photos')
    if not files or files[0].filename == '': flash('No file selected', 'danger'); return redirect(url_for('host_dashboard'))
    conn = get_db_connection()
    count = 0
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(f"camp_{camp_id}_{datetime.now().strftime('%M%S')}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            conn.execute("INSERT INTO camp_photos (camp_id, filename) VALUES (?, ?)", (camp_id, filename))
            count += 1
    conn.commit(); conn.close()
    if count > 0: flash(f'{count} Photos uploaded!', 'success')
    else: flash('Upload failed', 'danger')
    return redirect(url_for('host_dashboard'))

@app.route('/host/export_donors/<int:camp_id>')
def export_camp_donors(camp_id):
    if session.get('role') != 'host': return redirect(url_for('login'))
    conn = get_db_connection()
    camp = conn.execute("SELECT * FROM camps WHERE id = ? AND host_id = ?", (camp_id, session['user_id'])).fetchone()
    if not camp: conn.close(); return "Unauthorized", 403
    donors = conn.execute("SELECT d.name, d.blood_group, d.phone, d.email, d.city FROM camp_registrations cr LEFT JOIN donors d ON cr.donor_id = d.id WHERE cr.camp_id = ?", (camp_id,)).fetchall()
    conn.close()
    file_format = request.args.get('format', 'csv')
    if file_format == 'pdf':
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, f"Donor List: {camp['name']}", 0, 1, 'C'); pdf.ln(10)
        pdf.set_font("Arial", 'B', 10); headers = ['Name', 'Group', 'Phone', 'Email', 'City']; widths = [40, 15, 30, 60, 30]
        for i, h in enumerate(headers): pdf.cell(widths[i], 10, h, 1)
        pdf.ln(); pdf.set_font("Arial", '', 10)
        for d in donors:
            pdf.cell(widths[0], 10, str(d['name'] or 'Deleted'), 1); pdf.cell(widths[1], 10, str(d['blood_group'] or '-'), 1)
            pdf.cell(widths[2], 10, str(d['phone'] or '-'), 1); pdf.cell(widths[3], 10, str(d['email'] or '-'), 1); pdf.cell(widths[4], 10, str(d['city'] or '-'), 1); pdf.ln()
        response = make_response(pdf.output(dest='S').encode('latin-1')); response.headers['Content-Type'] = 'application/pdf'; response.headers['Content-Disposition'] = f'attachment; filename=Donors_{camp_id}.pdf'; return response
    else:
        si = StringIO(); cw = csv.writer(si); cw.writerow(['Name', 'Blood Group', 'Phone', 'Email', 'City'])
        for d in donors: cw.writerow([d['name'] or 'Deleted', d['blood_group'], d['phone'], d['email'], d['city']])
        out = make_response(si.getvalue()); out.headers["Content-Disposition"] = f"attachment; filename=Donors_{camp_id}.csv"; out.headers["Content-type"] = "text/csv"; return out

@app.route('/profile', methods=['GET', 'POST'])
def user_profile():
    if 'user_id' not in session: return redirect(url_for('login'))
    if session.get('role') == 'hospital': return redirect(url_for('hospital_dashboard'))
    if session.get('role') == 'host': return redirect(url_for('host_dashboard'))
    conn = get_db_connection()
    if request.method == 'POST':
        conn.execute('UPDATE donors SET name=?, email=?, city=?, address=? WHERE id=?', (request.form['name'], request.form['email'], request.form['city'], request.form['address'], session['user_id'])); conn.commit(); flash('Updated!', 'success')
    user = conn.execute('SELECT * FROM donors WHERE id = ?', (session['user_id'],)).fetchone()
    appointments = conn.execute("SELECT a.id, a.date, a.time_slot, a.status, h.name as location_name, 'Hospital' as type FROM appointments a JOIN hospitals h ON a.hospital_id = h.id WHERE a.donor_id = ?", (session['user_id'],)).fetchall()
    camp_bookings = conn.execute("SELECT cr.id, c.date, c.time as time_slot, cr.status, c.name as location_name, 'Camp' as type FROM camp_registrations cr JOIN camps c ON cr.camp_id = c.id WHERE cr.donor_id = ?", (session['user_id'],)).fetchall()
    all_bookings = sorted(appointments + camp_bookings, key=lambda x: x['date'], reverse=True)
    
    donations = conn.execute('''
        SELECT id, date, volume_ml, hospital, status, 'Manual' as source 
        FROM donations WHERE donor_id = ? 
        UNION ALL 
        SELECT a.id, a.date, 450 as volume_ml, h.name as hospital, a.status, 'Appointment' as source 
        FROM appointments a JOIN hospitals h ON a.hospital_id = h.id 
        WHERE a.donor_id = ? AND a.status = 'Verified' 
        ORDER BY date DESC
    ''', (session['user_id'], session['user_id'])).fetchall()
    
    hospitals = conn.execute("SELECT * FROM hospitals").fetchall()
    conn.close(); return render_template('user_profile.html', user=user, appointments=all_bookings, donations=donations, hospitals=hospitals)

@app.route('/change_password', methods=['POST'])
def change_password():
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    table = 'camp_hosts' if session.get('role') == 'host' else 'donors'
    if session.get('role') == 'hospital': table = 'hospitals'
        
    user = conn.execute(f'SELECT * FROM {table} WHERE id = ?', (session['user_id'],)).fetchone()
    if user and check_password_hash(user['password'], request.form['old_password']):
        conn.execute(f'UPDATE {table} SET password = ? WHERE id = ?', (generate_password_hash(request.form['new_password']), session['user_id'])); conn.commit(); flash('Password changed!', 'success')
    else: flash('Incorrect Old Password.', 'danger')
    conn.close()
    if session.get('role') == 'host': return redirect(url_for('host_dashboard'))
    if session.get('role') == 'hospital': return redirect(url_for('hospital_dashboard'))
    return redirect(url_for('user_profile'))

@app.route('/donate', methods=['POST'])
def donate():
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    
    donation_date = request.form.get('date', date.today())
    
    conn.execute('''INSERT INTO donations (donor_id, volume_ml, date, hospital, status) 
                    VALUES (?, ?, ?, ?, 'Pending')''', 
                 (session['user_id'], 450, donation_date, request.form['hospital_name']))
    
    conn.commit()
    conn.close()
    flash('Past donation logged! Awaiting verification from hospital.', 'info')
    return redirect(url_for('user_profile'))

@app.route('/book_appointment', methods=['GET', 'POST'])
def book_appointment():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    is_eligible, days_left = check_eligibility(session['user_id'])
    if not is_eligible: 
        flash(f'You cannot book yet. Please wait {days_left} days.', 'warning')
        return redirect(url_for('user_profile'))
        
    conn = get_db_connection()
    if request.method == 'POST':
        booking_type = request.form.get('booking_type') 
        if booking_type == 'hospital':
            hosp_id = request.form['hospital_id']
            book_date = request.form['date']
            time_slot = request.form['time_slot']
            
            try:
                conn.execute("BEGIN EXCLUSIVE TRANSACTION")
                
                MAX_SLOTS_PER_TIME = 5
                count_row = conn.execute('SELECT COUNT(*) FROM appointments WHERE hospital_id = ? AND date = ? AND time_slot = ?', (hosp_id, book_date, time_slot)).fetchone()
                current_bookings = count_row[0]
                
                if current_bookings >= MAX_SLOTS_PER_TIME:
                    conn.rollback()
                    flash(f'Sorry! The {time_slot} slot is fully booked. Please select another time.', 'danger')
                else:
                    conn.execute('INSERT INTO appointments (donor_id, hospital_id, date, time_slot) VALUES (?, ?, ?, ?)', (session['user_id'], hosp_id, book_date, time_slot))
                    
                    conn.commit()
                    flash('Booked successfully! Check your email for confirmation.', 'success')
                    
                    donor = conn.execute("SELECT name, email FROM donors WHERE id = ?", (session['user_id'],)).fetchone()
                    hosp = conn.execute("SELECT name FROM hospitals WHERE id = ?", (hosp_id,)).fetchone()
                    
                    send_confirmation_email(donor['email'], donor['name'], hosp['name'], book_date, time_slot)
                    
            except Exception as e:
                conn.rollback()
                flash('A database transaction error occurred. Please try again.', 'danger')
                
        elif booking_type == 'camp':
            camp_id = request.form['camp_id']
            exists = conn.execute("SELECT id FROM camp_registrations WHERE camp_id = ? AND donor_id = ?", (camp_id, session['user_id'])).fetchone()
            if exists: flash('Already registered.', 'warning')
            else: 
                conn.execute('INSERT INTO camp_registrations (camp_id, donor_id, booking_date) VALUES (?, ?, ?)', (camp_id, session['user_id'], date.today()))
                conn.commit()
                flash('Registered for the camp!', 'success')
        
        conn.close()
        return redirect(url_for('user_profile'))
        
    today_str = date.today().strftime('%Y-%m-%d')
    hospitals = conn.execute('SELECT * FROM hospitals').fetchall()
    camps = conn.execute("SELECT * FROM camps WHERE status='Upcoming' AND date >= ? ORDER BY date ASC", (today_str,)).fetchall()
    conn.close()
    return render_template('book_appointment.html', hospitals=hospitals, camps=camps, current_date=date.today())

# =========================================================================
# DBMS FEATURE: PUBLIC SOS EMERGENCY FINDER
# =========================================================================
@app.route('/public_sos', methods=['GET', 'POST'])
def public_sos():
    if request.method == 'POST':
        lat = request.form.get('lat')
        lng = request.form.get('lng')
        blood_group = request.form.get('blood_group')
        
        if not lat or not lng:
            flash("Please allow location access to use the SOS Radar.", "warning")
            return redirect(url_for('public_sos'))
            
        conn = get_db_connection()
        nearest_donors = conn.execute('''
            SELECT name, phone, blood_group, city, 
                   ROUND(haversine(?, ?, lat, lng), 2) as distance_km 
            FROM donors 
            WHERE blood_group = ? AND role != 'admin' AND lat IS NOT NULL
            ORDER BY distance_km ASC 
            LIMIT 5
        ''', (lat, lng, blood_group)).fetchall()
        conn.close()
        
        return render_template('public_sos.html', nearest_donors=nearest_donors, sos_bg=blood_group)
    
    return render_template('public_sos.html')

# =========================================================================
# DBMS FEATURE: SPATIAL QUERIES - HOSPITAL SOS
# =========================================================================
@app.route('/hospital/sos', methods=['POST'])
def hospital_sos():
    if session.get('role') != 'hospital': return redirect(url_for('login'))
    blood_group = request.form.get('blood_group')
    conn = get_db_connection()
    
    # Get the Hospital's exact GPS Coordinates
    hosp = conn.execute("SELECT lat, lng FROM hospitals WHERE id = ?", (session['user_id'],)).fetchone()
    
    # Execute Haversine Spatial Query directly inside SQLite
    nearest_donors = conn.execute('''
        SELECT name, phone, blood_group, city, 
               ROUND(haversine(?, ?, lat, lng), 2) as distance_km 
        FROM donors 
        WHERE blood_group = ? AND role != 'admin'
        ORDER BY distance_km ASC 
        LIMIT 5
    ''', (hosp['lat'], hosp['lng'], blood_group)).fetchall()
    
    # Reload regular dashboard data
    ts = date.today().strftime('%Y-%m-%d')
    upcoming = conn.execute("SELECT a.*, d.name as donor_name, d.blood_group, d.phone FROM appointments a JOIN donors d ON a.donor_id = d.id WHERE a.hospital_id = ? AND a.status = 'Scheduled' AND a.date > ? ORDER BY a.date ASC", (session['user_id'], ts)).fetchall()
    queue_appts = conn.execute("SELECT a.id, a.date, a.time_slot, 'Appointment' as type, d.name as donor_name, d.blood_group, d.phone, a.status FROM appointments a JOIN donors d ON a.donor_id = d.id WHERE a.hospital_id = ? AND a.status = 'Scheduled' AND a.date <= ?", (session['user_id'], ts)).fetchall()
    queue_manual = conn.execute("SELECT d.id, d.date, 'N/A' as time_slot, 'Manual Request' as type, u.name as donor_name, u.blood_group, u.phone, d.status FROM donations d JOIN donors u ON d.donor_id = u.id WHERE d.hospital = ? AND d.status = 'Pending'", (session['name'],)).fetchall()
    verification_queue = [dict(r) for r in queue_appts] + [dict(r) for r in queue_manual]
    verification_queue.sort(key=lambda x: x['date'])
    conn.close()
    
    flash(f'SOS Alert active. Found {len(nearest_donors)} nearby donors for {blood_group}.', 'danger')
    return render_template('hospital_dashboard.html', upcoming=upcoming, verification_queue=verification_queue, nearest_donors=nearest_donors, sos_bg=blood_group)

# =========================================================================
# NEW ROUTE: UPDATE EXTERNAL HOSPITAL STOCK
# =========================================================================
@app.route('/hospital/update_stock', methods=['POST'])
def hospital_update_stock():
    if session.get('role') != 'hospital': return redirect(url_for('login'))
    
    bg = request.form['blood_group']
    units = request.form['units']
    password = request.form['password']
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM hospitals WHERE id = ?', (session['user_id'],)).fetchone()
    
    if user and check_password_hash(user['password'], password):
        exists = conn.execute("SELECT id FROM hospital_stock WHERE hospital_id=? AND blood_group=?", (session['user_id'], bg)).fetchone()
        if exists:
            conn.execute("UPDATE hospital_stock SET units = units + ? WHERE id=?", (units, exists['id']))
        else:
            conn.execute("INSERT INTO hospital_stock (hospital_id, blood_group, units) VALUES (?, ?, ?)", (session['user_id'], bg, units))
        conn.commit()
        flash(f'Successfully added {units} units of {bg} to your external inventory!', 'success')
    else:
        flash('Invalid password! Stock update failed.', 'danger')
        
    conn.close()
    return redirect(url_for('hospital_dashboard'))

@app.route('/hospital/dashboard')
def hospital_dashboard(): 
    if session.get('role') != 'hospital': return redirect(url_for('login'))
    conn = get_db_connection(); today_str = date.today().strftime('%Y-%m-%d')
    upcoming = conn.execute("SELECT a.*, d.name as donor_name, d.blood_group, d.phone FROM appointments a JOIN donors d ON a.donor_id = d.id WHERE a.hospital_id = ? AND a.status = 'Scheduled' AND a.date > ? ORDER BY a.date ASC", (session['user_id'], today_str)).fetchall()
    queue_appts = conn.execute("SELECT a.id, a.date, a.time_slot, 'Appointment' as type, d.name as donor_name, d.blood_group, d.phone, a.status FROM appointments a JOIN donors d ON a.donor_id = d.id WHERE a.hospital_id = ? AND a.status = 'Scheduled' AND a.date <= ?", (session['user_id'], today_str)).fetchall()
    
    queue_manual = conn.execute("SELECT d.id, d.date, 'N/A' as time_slot, 'Manual Request' as type, u.name as donor_name, u.blood_group, u.phone, d.status FROM donations d JOIN donors u ON d.donor_id = u.id WHERE d.hospital = ? AND d.status = 'Pending'", (session['name'],)).fetchall()
    
    verification_queue = [dict(r) for r in queue_appts] + [dict(r) for r in queue_manual]
    verification_queue.sort(key=lambda x: x['date'])
    conn.close(); return render_template('hospital_dashboard.html', upcoming=upcoming, verification_queue=verification_queue)

@app.route('/hospital/export_donations')
def hospital_export_donations():
    if session.get('role') != 'hospital': return redirect(url_for('login'))
    
    file_format = request.args.get('format', 'csv')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    blood_group = request.args.get('blood_group')

    conn = get_db_connection()
    query = "SELECT d.date, u.name, u.blood_group, u.phone, d.volume_ml FROM donations d JOIN donors u ON d.donor_id=u.id WHERE d.hospital=? AND d.status='Approved'"
    params = [session['name']]

    if start_date: query += " AND d.date >= ?"; params.append(start_date)
    if end_date: query += " AND d.date <= ?"; params.append(end_date)
    if blood_group and blood_group != 'all': query += " AND u.blood_group = ?"; params.append(blood_group)

    donations = conn.execute(query, params).fetchall()
    conn.close()
    
    headers = ['Date', 'Name', 'Group', 'Phone', 'Volume']
    
    if file_format == 'pdf':
        pdf = FPDF('P', 'mm', 'A4'); pdf.add_page()
        pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, "Donation History", 0, 1, 'C'); pdf.ln(10)
        pdf.set_font("Arial", 'B', 10); widths = [30, 60, 20, 40, 20]
        for i, h in enumerate(headers): pdf.cell(widths[i], 10, h, 1)
        pdf.ln(); pdf.set_font("Arial", '', 10)
        for row in donations:
            pdf.cell(widths[0], 10, str(row['date']), 1); pdf.cell(widths[1], 10, str(row['name']), 1)
            pdf.cell(widths[2], 10, str(row['blood_group']), 1); pdf.cell(widths[3], 10, str(row['phone']), 1)
            pdf.cell(widths[4], 10, str(row['volume_ml']), 1); pdf.ln()
        response = make_response(pdf.output(dest='S').encode('latin-1')); response.headers['Content-Type'] = 'application/pdf'; response.headers['Content-Disposition'] = 'attachment; filename=Donations.pdf'; return response
    else:
        si = StringIO(); cw = csv.writer(si)
        cw.writerow(headers)
        for d in donations: cw.writerow([d['date'], d['name'], d['blood_group'], d['phone'], d['volume_ml']])
        out = make_response(si.getvalue()); out.headers['Content-Disposition'] = 'attachment; filename=Donations.csv'; out.headers['Content-Type'] = 'text/csv'; return out

@app.route('/hospital/export_appointments')
def hospital_export_appointments():
    if session.get('role') != 'hospital': return redirect(url_for('login'))
    
    file_format = request.args.get('format', 'csv')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    status = request.args.get('status')

    conn = get_db_connection()
    query = "SELECT a.date, a.time_slot, d.name, d.blood_group, d.phone, a.status FROM appointments a JOIN donors d ON a.donor_id = d.id WHERE a.hospital_id = ?"
    params = [session['user_id']]

    if start_date: query += " AND a.date >= ?"; params.append(start_date)
    if end_date: query += " AND a.date <= ?"; params.append(end_date)
    if status and status != 'all': query += " AND a.status = ?"; params.append(status)

    appointments = conn.execute(query, params).fetchall()
    conn.close()
    
    headers = ['Date', 'Time', 'Name', 'Group', 'Phone', 'Status']
    
    if file_format == 'pdf':
        pdf = FPDF('L', 'mm', 'A4'); pdf.add_page()
        pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, "Appointments Log", 0, 1, 'C'); pdf.ln(10)
        pdf.set_font("Arial", 'B', 10); widths = [30, 40, 60, 20, 40, 30]
        for i, h in enumerate(headers): pdf.cell(widths[i], 10, h, 1)
        pdf.ln(); pdf.set_font("Arial", '', 10)
        for row in appointments:
            pdf.cell(widths[0], 10, str(row['date']), 1); pdf.cell(widths[1], 10, str(row['time_slot']), 1)
            pdf.cell(widths[2], 10, str(row['name']), 1); pdf.cell(widths[3], 10, str(row['blood_group']), 1)
            pdf.cell(widths[4], 10, str(row['phone']), 1); pdf.cell(widths[5], 10, str(row['status']), 1); pdf.ln()
        response = make_response(pdf.output(dest='S').encode('latin-1')); response.headers['Content-Type'] = 'application/pdf'; response.headers['Content-Disposition'] = 'attachment; filename=Appointments.pdf'; return response
    else:
        si = StringIO(); cw = csv.writer(si); cw.writerow(headers)
        for a in appointments: cw.writerow([a['date'], a['time_slot'], a['name'], a['blood_group'], a['phone'], a['status']])
        out = make_response(si.getvalue()); out.headers['Content-Disposition'] = 'attachment; filename=Appointments.csv'; out.headers['Content-Type'] = 'text/csv'; return out

@app.route('/hospital/verify/<int:id>/<action>/<type>')
def verify_donation(id, action, type):
    if session.get('role') != 'hospital': return redirect(url_for('login'))
    conn = get_db_connection()
    status = 'Verified' if action == 'approve' else 'Rejected'
    if type == 'Appointment':
        conn.execute('UPDATE appointments SET status = ? WHERE id = ?', (status, id))
        if status == 'Verified':
            data = conn.execute('SELECT * FROM appointments WHERE id=?', (id,)).fetchone()
            hosp = conn.execute('SELECT name FROM hospitals WHERE id=?', (data['hospital_id'],)).fetchone()
            exists = conn.execute('SELECT id FROM donations WHERE donor_id=? AND date=?', (data['donor_id'], data['date'])).fetchone()
            if not exists: conn.execute('INSERT INTO donations (donor_id, date, volume_ml, hospital, status) VALUES (?, ?, ?, ?, ?)', (data['donor_id'], data['date'], 450, hosp['name'], 'Approved'))
    elif type == 'Manual Request':
        db_status = 'Approved' if action == 'approve' else 'Rejected'
        conn.execute('UPDATE donations SET status = ? WHERE id = ?', (db_status, id))
    conn.commit(); conn.close(); return redirect(url_for('hospital_dashboard'))

@app.route('/certificate/<int:appt_id>')
def download_certificate(appt_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    data = conn.execute('SELECT a.date, d.name, h.name as hospital_name, d.blood_group FROM appointments a JOIN donors d ON a.donor_id = d.id JOIN hospitals h ON a.hospital_id = h.id WHERE a.id = ?', (appt_id,)).fetchone()
    if not data: data = conn.execute('SELECT d.date, u.name, d.hospital as hospital_name, u.blood_group FROM donations d JOIN donors u ON d.donor_id = u.id WHERE d.id = ?', (appt_id,)).fetchone()
    conn.close()
    if not data: return "Certificate not available", 403
    pdf = FPDF('L', 'mm', 'A4'); pdf.add_page(); pdf.set_fill_color(178, 34, 34); pdf.rect(0, 0, 297, 15, 'F'); pdf.rect(0, 195, 297, 15, 'F'); pdf.set_y(40); pdf.set_font("Arial", 'B', 32); pdf.set_text_color(139, 0, 0); pdf.cell(0, 15, "BLOOD DONATION CERTIFICATE", 0, 1, 'C'); pdf.set_font("Arial", '', 12); pdf.set_text_color(80, 80, 80); pdf.ln(15); pdf.cell(0, 10, "This certificate is awarded to", 0, 1, 'C'); pdf.set_font("Arial", 'B', 40); pdf.set_text_color(0, 0, 0); pdf.ln(5); pdf.cell(0, 20, data['name'], 0, 1, 'C'); pdf.set_font("Arial", '', 14); pdf.ln(15); pdf.multi_cell(0, 10, f"For the voluntary blood donation (Group: {data['blood_group']}).\nYour contribution brings hope and saves lives.", 0, 'C'); pdf.set_y(150); pdf.set_font("Arial", 'B', 12); pdf.cell(0, 10, f"Date: {data['date']}", 0, 1, 'C'); pdf.ln(8); pdf.cell(0, 10, f"Location: {data['hospital_name']}", 0, 1, 'C'); response = make_response(pdf.output(dest='S').encode('latin-1')); response.headers['Content-Type'] = 'application/pdf'; response.headers['Content-Disposition'] = 'attachment; filename=Certificate.pdf'; return response

# =========================================================================
# NEW ROUTE: ADMIN ADD MANUAL UNITS TO USER
# =========================================================================
@app.route('/admin/add_donation_units', methods=['POST'])
def admin_add_donation_units():
    if session.get('role') != 'admin': return redirect(url_for('admin_login'))
    user_id = request.form['user_id']
    volume_ml = request.form['volume_ml']
    hospital_name = request.form['hospital_name']
    
    conn = get_db_connection()
    conn.execute("INSERT INTO donations (donor_id, volume_ml, date, hospital, status) VALUES (?, ?, ?, ?, 'Approved')", 
                 (user_id, volume_ml, date.today().strftime('%Y-%m-%d'), hospital_name))
    conn.commit()
    conn.close()
    flash(f'Successfully added {volume_ml}ml for the donor.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('admin_login'))
    conn = get_db_connection()
    donors = conn.execute("SELECT * FROM donors WHERE role != 'admin'").fetchall()
    hospitals = conn.execute("SELECT * FROM hospitals").fetchall()
    hosts = conn.execute("SELECT * FROM camp_hosts ORDER BY organization_name ASC").fetchall()
    today_str = date.today().strftime('%Y-%m-%d')
    ended_camps = conn.execute("SELECT * FROM camps WHERE date < ? ORDER BY date DESC", (today_str,)).fetchall()
    admin_info = conn.execute("SELECT * FROM donors WHERE id = ?", (session['user_id'],)).fetchone()
    hospital_stats = conn.execute('''SELECT h.name as hospital, COUNT(a.id) as total_units FROM hospitals h LEFT JOIN appointments a ON h.id = a.hospital_id AND a.status='Verified' GROUP BY h.id''').fetchall()
    pending_appts = conn.execute('''SELECT a.date, d.name as donor, d.phone, h.name as hospital_name FROM appointments a JOIN donors d ON a.donor_id = d.id JOIN hospitals h ON a.hospital_id = h.id WHERE a.status = 'Scheduled' ORDER BY h.name ASC, a.date ASC''').fetchall()
    verified_appts = conn.execute('''SELECT a.date, d.name as donor, d.phone, h.name as hospital_name FROM appointments a JOIN donors d ON a.donor_id = d.id JOIN hospitals h ON a.hospital_id = h.id WHERE a.status = 'Verified' ORDER BY h.name ASC, a.date DESC''').fetchall()
    
    gallery_photos = conn.execute('''
        SELECT cp.id, cp.filename, c.name as camp_name, c.date 
        FROM camp_photos cp 
        JOIN camps c ON cp.camp_id = c.id 
        ORDER BY c.date DESC
    ''').fetchall()

    all_camps = conn.execute("SELECT c.*, h.organization_name, h.leader_name, h.phone FROM camps c JOIN camp_hosts h ON c.host_id = h.id ORDER BY c.date DESC").fetchall()
    search = request.args.get('search', ''); city = request.args.get('city', ''); blood_group = request.args.get('blood_group', ''); hospital_search = request.args.get('hospital_name', '')
    hospital_donors = []
    if hospital_search:
        hospital_donors = conn.execute('''SELECT d.name, d.phone, d.email, d.city, a.date FROM appointments a JOIN donors d ON a.donor_id = d.id JOIN hospitals h ON a.hospital_id = h.id WHERE h.name LIKE ? AND a.status='Verified' ''', (f'%{hospital_search}%',)).fetchall()
    
    audit_logs = conn.execute("SELECT * FROM security_audit_log ORDER BY action_timestamp DESC LIMIT 20").fetchall()
    
    ai_predictions = conn.execute('''
        SELECT h.name as hospital,
               IFNULL(SUM(d.volume_ml), 0) as current_stock,
               ROUND(AVG(IFNULL(SUM(d.volume_ml), 0)) OVER (), 1) as global_avg,
               CASE 
                   WHEN IFNULL(SUM(d.volume_ml), 0) < (AVG(IFNULL(SUM(d.volume_ml), 0)) OVER () * 0.7) THEN '🚨 CRITICAL SHORTAGE'
                   WHEN IFNULL(SUM(d.volume_ml), 0) > (AVG(IFNULL(SUM(d.volume_ml), 0)) OVER () * 1.5) THEN '🌟 SURPLUS'
                   ELSE '✅ STABLE' 
               END as ai_status
        FROM hospitals h
        LEFT JOIN donations d ON h.name = d.hospital AND d.status = 'Approved'
        GROUP BY h.name
        ORDER BY current_stock ASC
    ''').fetchall()
    
    conn.close()
    return render_template('admin_dashboard.html', donors=donors, hospitals=hospitals, hosts=hosts, hospital_stats=hospital_stats, pending_appts=pending_appts, verified_appts=verified_appts, all_camps=all_camps, ended_camps=ended_camps, admin_info=admin_info, gallery_photos=gallery_photos, audit_logs=audit_logs, ai_predictions=ai_predictions)

@app.route('/admin/update_profile', methods=['POST'])
def update_admin_profile():
    if session.get('role') != 'admin': return redirect(url_for('admin_login'))
    conn = get_db_connection()
    try:
        if request.form.get('password'): conn.execute('UPDATE donors SET name=?, email=?, phone=?, password=? WHERE id=?', (request.form['name'], request.form['email'], request.form['phone'], generate_password_hash(request.form['password']), session['user_id']))
        else: conn.execute('UPDATE donors SET name=?, email=?, phone=? WHERE id=?', (request.form['name'], request.form['email'], request.form['phone'], session['user_id']))
        conn.commit(); session['name'] = request.form['name']; flash('Admin Profile Updated!', 'success')
    except Exception as e: flash(f'Error: {e}', 'danger')
    conn.close(); return redirect(url_for('admin_dashboard'))

@app.route('/admin/add_user', methods=['GET', 'POST'])
def add_user():
    if session.get('role') != 'admin': return redirect(url_for('admin_login'))
    if request.method == 'POST':
        conn = get_db_connection()
        try: conn.execute("INSERT INTO donors (name, email, phone, password, blood_group, city, age, weight, address, role) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'user')", (request.form['name'], request.form['email'], request.form['phone'], generate_password_hash(request.form['password']), request.form['blood_group'], request.form['city'], request.form['age'], request.form['weight'], request.form['address'])); conn.commit(); flash('User Added!', 'success')
        except: flash('Error adding user', 'danger')
        conn.close(); return redirect(url_for('admin_dashboard'))
    return render_template('add_user.html')

@app.route('/admin/add_host', methods=['GET', 'POST'])
def add_host():
    if session.get('role') != 'admin': return redirect(url_for('admin_login'))
    if request.method == 'POST':
        conn = get_db_connection()
        try: conn.execute("INSERT INTO camp_hosts (organization_name, leader_name, email, phone, aadhar_number, password, city, address) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (request.form['organization_name'], request.form['leader_name'], request.form['email'], request.form['phone'], request.form['aadhar_number'], generate_password_hash(request.form['password']), request.form['city'], request.form['address'])); conn.commit(); flash('Host Added!', 'success')
        except: flash('Error', 'danger')
        conn.close(); return redirect(url_for('admin_dashboard'))
    return render_template('add_host.html')

@app.route('/admin/add_hospital', methods=['GET', 'POST'])
def add_hospital():
    if session.get('role') != 'admin': return redirect(url_for('admin_login'))
    if request.method == 'POST':
        conn = get_db_connection()
        try: conn.execute("INSERT INTO hospitals (name, email, password, type, lat, lng) VALUES (?, ?, ?, ?, ?, ?)", (request.form['name'], request.form['email'], generate_password_hash(request.form['password']), request.form['type'], request.form['lat'], request.form['lng'])); conn.commit(); flash('Hospital Added!', 'success')
        except: flash('Error', 'danger')
        conn.close(); return redirect(url_for('admin_dashboard'))
    return render_template('add_hospital.html')

@app.route('/admin/edit_hospital/<int:id>', methods=['GET', 'POST'])
def edit_hospital(id):
    if session.get('role') != 'admin': return redirect(url_for('admin_login'))
    conn = get_db_connection()
    if request.method == 'POST':
        pw = request.form.get('password')
        if pw: conn.execute('UPDATE hospitals SET name=?, email=?, type=?, lat=?, lng=?, password=? WHERE id=?', (request.form['name'], request.form['email'], request.form['type'], request.form['lat'], request.form['lng'], generate_password_hash(pw), id))
        else: conn.execute('UPDATE hospitals SET name=?, email=?, type=?, lat=?, lng=? WHERE id=?', (request.form['name'], request.form['email'], request.form['type'], request.form['lat'], request.form['lng'], id))
        conn.commit(); flash('Updated!', 'success'); return redirect(url_for('admin_dashboard'))
    hospital = conn.execute('SELECT * FROM hospitals WHERE id = ?', (id,)).fetchone(); conn.close()
    return render_template('edit_hospital.html', hospital=hospital)

@app.route('/admin/delete_hospital/<int:id>')
def delete_hospital(id):
    if session.get('role') != 'admin': return redirect(url_for('admin_login'))
    conn = get_db_connection(); conn.execute('DELETE FROM hospitals WHERE id = ?', (id,)); conn.commit(); conn.close()
    flash('Hospital Deleted', 'success'); return redirect(url_for('admin_dashboard'))

@app.route('/admin/edit/<int:id>', methods=['GET', 'POST'])
def edit_user(id):
    if session.get('role') != 'admin': return redirect(url_for('admin_login'))
    conn = get_db_connection()
    if request.method == 'POST':
        pw = request.form.get('password')
        if pw: conn.execute('UPDATE donors SET name=?, email=?, phone=?, city=?, blood_group=?, password=? WHERE id=?', (request.form['name'], request.form['email'], request.form['phone'], request.form['city'], request.form['blood_group'], generate_password_hash(pw), id))
        else: conn.execute('UPDATE donors SET name=?, email=?, phone=?, city=?, blood_group=? WHERE id=?', (request.form['name'], request.form['email'], request.form['phone'], request.form['city'], request.form['blood_group'], id))
        conn.commit(); return redirect(url_for('admin_dashboard'))
    donor = conn.execute('SELECT * FROM donors WHERE id = ?', (id,)).fetchone(); conn.close()
    return render_template('edit_user.html', donor=donor)

@app.route('/admin/delete/<int:id>')
def delete_user(id):
    if session.get('role') != 'admin': return redirect(url_for('admin_login'))
    conn = get_db_connection(); conn.execute('DELETE FROM donors WHERE id = ?', (id,)); conn.commit(); conn.close()
    flash('User Deleted', 'success'); return redirect(url_for('admin_dashboard'))

@app.route('/admin/edit_host/<int:id>', methods=['GET', 'POST'])
def edit_host(id):
    if session.get('role') != 'admin': return redirect(url_for('admin_login'))
    conn = get_db_connection()
    if request.method == 'POST':
        pw = request.form.get('password')
        if pw: conn.execute('UPDATE camp_hosts SET organization_name=?, leader_name=?, email=?, phone=?, aadhar_number=?, city=?, address=?, password=? WHERE id=?', (request.form['organization_name'], request.form['leader_name'], request.form['email'], request.form['phone'], request.form['aadhar_number'], request.form['city'], request.form['address'], generate_password_hash(pw), id))
        else: conn.execute('UPDATE camp_hosts SET organization_name=?, leader_name=?, email=?, phone=?, aadhar_number=?, city=?, address=? WHERE id=?', (request.form['organization_name'], request.form['leader_name'], request.form['email'], request.form['phone'], request.form['aadhar_number'], request.form['city'], request.form['address'], id))
        conn.commit(); flash('Host Updated', 'success'); return redirect(url_for('admin_dashboard'))
    host = conn.execute('SELECT * FROM camp_hosts WHERE id = ?', (id,)).fetchone(); conn.close()
    return render_template('edit_host.html', host=host)

@app.route('/admin/delete_host/<int:id>')
def delete_host(id):
    if session.get('role') != 'admin': return redirect(url_for('admin_login'))
    conn = get_db_connection(); conn.execute('DELETE FROM camps WHERE host_id = ?', (id,)); conn.execute('DELETE FROM camp_hosts WHERE id = ?', (id,)); conn.commit(); conn.close(); flash('Deleted', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_photo/<int:id>')
def delete_camp_photo_admin(id):
    if session.get('role') != 'admin': return redirect(url_for('admin_login'))
    conn = get_db_connection()
    photo = conn.execute("SELECT filename FROM camp_photos WHERE id = ?", (id,)).fetchone()
    
    if photo:
        try: os.remove(os.path.join(app.config['UPLOAD_FOLDER'], photo['filename']))
        except OSError: pass
        conn.execute("DELETE FROM camp_photos WHERE id = ?", (id,))
        conn.commit()
        flash('Photo deleted successfully.', 'success')
    else:
        flash('Photo not found.', 'danger')
        
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/export_report')
def export_report():
    if session.get('role') != 'admin': return redirect(url_for('admin_login'))
    conn = get_db_connection()
    report_type = request.args.get('type')
    file_format = request.args.get('file_format', 'csv')
    
    rows = []; headers = []; widths = []
    filename = f"Report_{report_type}"

    if report_type == 'camp_donors':
        camp_id = request.args.get('camp_id')
        camp = conn.execute("SELECT name FROM camps WHERE id=?", (camp_id,)).fetchone()
        filename = f"Camp_Donors_{camp['name']}" if camp else "Camp_Donors"
        rows = conn.execute("SELECT d.name, d.blood_group, d.phone, d.email, d.city FROM camp_registrations cr LEFT JOIN donors d ON cr.donor_id = d.id WHERE cr.camp_id = ?", (camp_id,)).fetchall()
        headers = ['Name', 'Group', 'Phone', 'Email', 'City']; widths = [40, 20, 35, 60, 35]

    elif report_type == 'donations':
        rows = conn.execute('''SELECT d.date, u.name, d.volume_ml, d.hospital, d.status 
                               FROM donations d JOIN donors u ON d.donor_id = u.id ORDER BY d.date DESC''').fetchall()
        headers = ['Date', 'Donor', 'Vol (ml)', 'Hospital', 'Status']; widths = [30, 50, 20, 60, 30]

    elif report_type == 'hospitals' or report_type == 'hospitals_list':
        rows = conn.execute('''SELECT h.name, h.type, h.email, COUNT(d.id) as total_units 
                               FROM hospitals h LEFT JOIN donations d ON h.name = d.hospital AND d.status='Approved' 
                               GROUP BY h.id ORDER BY total_units DESC''').fetchall()
        headers = ['Hospital', 'Type', 'Email', 'Collected']; widths = [80, 25, 60, 25]

    elif report_type == 'camps_history':
        rows = conn.execute("SELECT date, name, location_name, city FROM camps ORDER BY date DESC").fetchall()
        headers = ['Date', 'Event', 'Location', 'City']; widths = [30, 60, 60, 40]

    elif report_type == 'users_list':
        rows = conn.execute("SELECT name, email, phone, blood_group, city FROM donors WHERE role!='admin'").fetchall()
        headers = ['Name', 'Email', 'Phone', 'Group', 'City']; widths = [40, 60, 30, 20, 40]

    elif report_type == 'hosts_list':
        rows = conn.execute("SELECT organization_name, leader_name, email, phone, city FROM camp_hosts").fetchall()
        headers = ['Org Name', 'Leader', 'Email', 'Phone', 'City']; widths = [50, 40, 50, 30, 20]

    conn.close()

    if file_format == 'pdf':
        pdf = FPDF('L', 'mm', 'A4'); pdf.add_page(); pdf.set_font("Arial", 'B', 14); pdf.cell(0, 10, f"Report: {report_type}", 0, 1, 'C'); pdf.ln(10)
        pdf.set_font("Arial", 'B', 10)
        for i, h in enumerate(headers): 
            w = widths[i] if i < len(widths) else 30
            pdf.cell(w, 10, h, 1)
        pdf.ln(); pdf.set_font("Arial", '', 10)
        for row in rows:
            for i, item in enumerate(row):
                w = widths[i] if i < len(widths) else 30
                text = str(item) if item else "N/A"
                if pdf.get_string_width(text) > w: text = text[:int(w/2)] + "..."
                pdf.cell(w, 10, text, 1)
            pdf.ln()
        response = make_response(pdf.output(dest='S').encode('latin-1')); response.headers['Content-Type'] = 'application/pdf'; response.headers['Content-Disposition'] = f'attachment; filename={filename}.pdf'; return response
    else:
        si = StringIO(); cw = csv.writer(si); cw.writerow(headers)
        for r in rows: cw.writerow([str(item) if item else "N/A" for item in r])
        out = make_response(si.getvalue()); out.headers['Content-Disposition'] = f'attachment; filename={filename}.csv'; out.headers['Content-Type'] = 'text/csv'; return out

@app.route('/about')
def about(): return render_template('about.html')
@app.route('/contact')
def contact(): return render_template('contact.html')
@app.route('/map')
def map_page(): return render_template('map.html')

# =========================================================================
# MAP API: UPDATED TO REFLECT EXTERNAL + INTERNAL STOCK
# =========================================================================
@app.route('/api/blood-stock')
def get_map(): 
    conn = get_db_connection()
    today_str = date.today().strftime('%Y-%m-%d')
    
    # Calculate Internal verified donations + External uploaded stock
    hospitals = conn.execute('''
        SELECT h.id, h.name, h.lat, h.lng, h.type, h.email as contact, 'hospital' as marker_type, 'N/A' as host, 
        (SELECT COUNT(*) FROM donations d WHERE d.hospital = h.name AND d.status = 'Approved') as internal_stock,
        IFNULL((SELECT SUM(units) FROM hospital_stock hs WHERE hs.hospital_id = h.id), 0) as external_stock
        FROM hospitals h
    ''').fetchall()
    
    camps = conn.execute("SELECT c.name, c.lat, c.lng, 'Camp' as type, 'camp' as marker_type, c.estimated_participants as capacity, ch.organization_name as host, ch.phone as contact, (SELECT COUNT(*) FROM camp_registrations cr WHERE cr.camp_id = c.id) as registered_count FROM camps c JOIN camp_hosts ch ON c.host_id = ch.id WHERE c.status='Upcoming' AND c.date >= ?", (today_str,)).fetchall()
    conn.close()
    
    data = []
    for h in hospitals:
        total_stock = h['internal_stock'] + h['external_stock']
        st = f"{total_stock} Units" if total_stock > 0 else "Low Stock"
        info = f"<div style='text-align:center;'><b>🏥 {h['name']}</b><br><span style='color:grey;'>{h['type']} Hospital</span><br><div style='margin:5px 0; background:#ffebeb; border:1px solid #ffcccc;'><b>🩸 Total Stock:</b> <span style='color:red;'>{st}</span></div>📞 {h['contact']}</div>"
        d = dict(h); d['popup_info'] = info; data.append(d)
        
    for c in camps:
        info = f"<div style='text-align:center;'><b>⛺ {c['name']}</b><br><span style='color:grey;'>Host: {c['host']}</span><br><div style='margin:5px 0; background:#e6fffa; border:1px solid #b3ffec;'><b>📝 Registered:</b> <span style='color:green;'>{c['registered_count']} / {c['capacity']}</span></div>📞 {c['contact']}</div>"
        d = dict(c); d['popup_info'] = info; data.append(d)
        
    return jsonify(data) 

if __name__ == '__main__':
    app.run(debug=True, port=5000)