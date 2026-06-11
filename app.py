import os
import csv
import io
import base64
import re
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from config import Config
from models import db, User, Report
from datetime import datetime, timezone, timedelta
import uuid
import random
from datetime import timedelta as td


app = Flask(__name__)
app.config.from_object(Config)
app.config['WTF_CSRF_ENABLED'] = False

db.init_app(app)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

# ==================== PASSWORD VALIDATION ====================

def validate_password_strict(password):
    if not password:
        return False, "Password is required"
    
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter (A-Z)"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter (a-z)"
    
    if not re.search(r'\d', password):
        return False, "Password must contain at least one digit (0-9)"
    
    if not re.search(r'[!@#$%^&*()_+\-=\$\${};:\'",.<>?/\\|`~]', password):
        return False, "Password must contain at least one special character (!@#$%^&*...)"
    
    return True, None

def generate_otp():
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])

def send_email_otp(email, otp):
    """Send OTP via email with proper error handling"""
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        mail_server = app.config.get('MAIL_SERVER')
        mail_port = app.config.get('MAIL_PORT', 587)
        mail_username = app.config.get('MAIL_USERNAME')
        mail_password = app.config.get('MAIL_PASSWORD')
        
        # Check if config exists
        if not all([mail_server, mail_username, mail_password]):
            print("Email configuration missing!")
            return False
        
        msg = MIMEMultipart()
        msg['From'] = mail_username
        msg['To'] = email
        msg['Subject'] = 'LEAPO Password Reset OTP'
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #f59e0b;">Password Reset Request</h2>
            <p>Your OTP for password reset is:</p>
            <h1 style="color: #f59e0b; letter-spacing: 5px;">{otp}</h1>
            <p>This OTP is valid for 10 minutes.</p>
            <p>If you didn't request this, please ignore this email.</p>
        </body>
        </html>
        """
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(mail_server, mail_port)
        server.ehlo()
        server.starttls()
        server.login(mail_username, mail_password)
        server.sendmail(mail_username, email, msg.as_string())
        server.quit()
        
        print(f"✓ Email sent successfully to {email}")
        return True
        
    except smtplib.SMTPAuthenticationError:
        print("Email error: Authentication failed - check username/password")
        return False
    except smtplib.SMTPConnectError:
        print("Email error: Could not connect to SMTP server")
        return False
    except Exception as e:
        print(f"Email error: {e}")
        return False
# ==================== IMAGE ROUTES ====================

@app.route('/image/<int:report_id>')
@login_required
def get_image(report_id):
    report = Report.query.get_or_404(report_id)
    
    if report.image_data:
        response = make_response(report.image_data)
        
        if report.image_type == 'png':
            response.headers['Content-Type'] = 'image/png'
        elif report.image_type == 'gif':
            response.headers['Content-Type'] = 'image/gif'
        else:
            response.headers['Content-Type'] = 'image/jpeg'
        
        response.headers['Content-Disposition'] = f'inline; filename={report.image_name}'
        return response
    
    return "Image not found", 404


@app.route('/image_thumb/<int:report_id>')
@login_required
def get_image_thumb(report_id):
    report = Report.query.get_or_404(report_id)
    
    if report.image_data:
        try:
            from PIL import Image
            
            img = Image.open(io.BytesIO(report.image_data))
            img.thumbnail((200, 200), Image.LANCZOS)
            
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=70)
            output.seek(0)
            
            response = make_response(output.getvalue())
            response.headers['Content-Type'] = 'image/jpeg'
            return response
        except Exception as e:
            print(f"Thumbnail error: {e}")
            response = make_response(report.image_data)
            response.headers['Content-Type'] = 'image/jpeg'
            return response
    
    return "Image not found", 404

# ==================== FORGOT PASSWORD ROUTES ====================

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        
        user = User.query.filter_by(email=email).first()
        
        if user:
            otp = generate_otp()
            user.otp_code = otp
            user.otp_expiry = datetime.now() + td(minutes=10)
            db.session.commit()
            
            # Try to send email, but don't fail if it doesn't work
            email_sent = send_email_otp(email, otp)
            
            # Always show success (demo mode on deployment)
            flash(f'OTP sent! Code: {otp}', 'success')
            
            return redirect(url_for('verify_otp', user_id=user.id))
        else:
            flash('Email not found! Please register first.', 'error')
    
    return render_template('forgot_password.html')

@app.route('/verify_otp/<int:user_id>', methods=['GET', 'POST'])
def verify_otp(user_id):
    user = User.query.get(user_id)
    
    if not user:
        flash('Invalid request!', 'error')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        otp = request.form.get('otp')
        
        if user.otp_code and user.otp_expiry:
            if user.otp_code == otp and user.otp_expiry > datetime.now():
                user.otp_code = None
                user.otp_expiry = None
                db.session.commit()
                
                flash('OTP verified! Please set your new password.', 'success')
                return redirect(url_for('reset_password', user_id=user.id))
            else:
                flash('Invalid or expired OTP!', 'error')
        else:
            flash('No OTP found. Please request a new one.', 'error')
    
    return render_template('verify_otp.html', user_id=user_id)

@app.route('/reset_password/<int:user_id>', methods=['GET', 'POST'])
def reset_password(user_id):
    user = User.query.get(user_id)
    
    if not user:
        flash('Invalid request!', 'error')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password != confirm_password:
            flash('Passwords do not match!', 'error')
            return render_template('reset_password.html', user_id=user_id)
        
        is_valid, error_message = validate_password_strict(new_password)
        if not is_valid:
            flash(error_message, 'error')
            return render_template('reset_password.html', user_id=user_id)
        
        user.set_password(new_password)
        db.session.commit()
        
        flash('Password reset successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('reset_password.html', user_id=user_id)

# ==================== DOWNLOAD PDF ROUTE ====================

@app.route('/download_report_pdf/<int:report_id>')
@login_required
def download_report_pdf(report_id):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    
    report = Report.query.get_or_404(report_id)
    
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height - 50, f"LEAPO Report #{report.id}")
    c.line(50, height - 55, 550, height - 55)
    
    y = height - 80
    
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Worker:")
    c.setFont("Helvetica", 12)
    c.drawString(150, y, str(report.worker.username))
    
    y -= 18
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Employee ID:")
    c.setFont("Helvetica", 12)
    c.drawString(150, y, str(report.worker.emp_id))
    
    y -= 18
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Department:")
    c.setFont("Helvetica", 12)
    c.drawString(150, y, str(report.worker.department or "N/A"))
    
    y -= 18
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Status:")
    c.setFont("Helvetica", 12)
    c.drawString(150, y, str(report.status.upper()))
    
    y -= 18
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Date:")
    c.setFont("Helvetica", 12)
    c.drawString(150, y, report.created_at.strftime("%d %b, %Y at %H:%M"))
    
    y -= 18
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Location:")
    c.setFont("Helvetica", 12)
    loc = f"{report.latitude}, {report.longitude}" if report.latitude and report.longitude else "Not Available"
    c.drawString(150, y, loc)
    
    y -= 30
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Issue Description:")
    y -= 18
    c.setFont("Helvetica", 11)
    
    text = report.issue_description
    for line in [text[i:i+80] for i in range(0, len(text), 80)]:
        c.drawString(50, y, line)
        y -= 14
    
    if report.image_data:
        y -= 25
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "Attached Image:")
        
        try:
            from PIL import Image
            import tempfile
            
            img = Image.open(io.BytesIO(report.image_data))
            img.thumbnail((300, 300))
            
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                img.save(tmp.name, format='JPEG')
                tmp_path = tmp.name
            
            if y < 150:
                c.showPage()
                c.setFont("Helvetica", 12)
                y = height - 50
            
            c.drawImage(tmp_path, 50, y - 200, width=150, height=150, preserveAspectRatio=True)
            os.unlink(tmp_path)
            
        except Exception as e:
            print(f"Error adding image to PDF: {e}")
            y -= 18
            c.setFont("Helvetica", 10)
            c.drawString(50, y, "[Image attached]")
    
    c.showPage()
    c.save()
    
    buffer.seek(0)
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=report_{report.id}.pdf'
    
    return response

# ==================== DOWNLOAD ALL REPORTS ====================

@app.route('/download_reports')
@login_required
def download_reports():
    if current_user.role != 'admin':
        return redirect(url_for('worker_dashboard'))
    
    from datetime import timedelta, timezone
    
    format_type = request.args.get('format', 'csv')
    
    # Get same filters as admin_dashboard
    filter_date_filter = request.args.get('date_filter')
    filter_date_from = request.args.get('date_from')
    filter_date_to = request.args.get('date_to')
    filter_area = request.args.get('area')
    filter_emp_id = request.args.get('emp_id')
    
    # Use IST timezone
    ist_offset = timedelta(hours=5, minutes=30)
    ist_timezone = timezone(ist_offset)
    ist_now = datetime.now(ist_timezone)
    today = ist_now.date()
    
    # Apply same filters as admin_dashboard
    query = Report.query.join(User, Report.worker_id == User.id)
    
    if filter_date_filter == 'yesterday':
        yesterday = today - timedelta(days=1)
        from_date = datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, 0)
        to_date = datetime(today.year, today.month, today.day, 0, 0, 0)
        query = query.filter(Report.created_at >= from_date, Report.created_at < to_date)
    elif filter_date_filter == '3days':
        from_date = datetime.combine(today - timedelta(days=3), datetime.min.time())
        query = query.filter(Report.created_at >= from_date)
    elif filter_date_filter == '7days':
        from_date = datetime.combine(today - timedelta(days=7), datetime.min.time())
        query = query.filter(Report.created_at >= from_date)
    elif filter_date_filter == '1month':
        from_date = datetime.combine(today - timedelta(days=30), datetime.min.time())
        query = query.filter(Report.created_at >= from_date)
    elif filter_date_filter == 'custom':
        if filter_date_from:
            try:
                from_date = datetime.strptime(filter_date_from, '%Y-%m-%d')
                query = query.filter(Report.created_at >= from_date)
            except:
                pass
        if filter_date_to:
            try:
                to_date = datetime.strptime(filter_date_to, '%Y-%m-%d')
                to_date = to_date + timedelta(days=1)
                query = query.filter(Report.created_at < to_date)
            except:
                pass
    
    if filter_area:
        query = query.filter(User.area == filter_area)
    
    if filter_emp_id:
        query = query.filter(User.emp_id.ilike(f'%{filter_emp_id}%'))
    
    reports = query.order_by(Report.created_at.desc()).all()
    
    if format_type == 'pdf':
        # PDF download code (same as before)
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        
        c.setFont("Helvetica-Bold", 18)
        c.drawString(50, height - 50, "LEAPO Reports")
        c.line(50, height - 55, 550, height - 55)
        
        y = height - 80
        
        for report in reports:
            if y < 150:
                c.showPage()
                c.setFont("Helvetica", 12)
                y = height - 50
            
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, y, f"Report #{report.id} - {report.status.upper()}")
            y -= 15
            
            c.setFont("Helvetica", 10)
            c.drawString(50, y, f"Worker: {report.worker.username} (ID: {report.worker.emp_id}) | Dept: {report.worker.department or 'N/A'} | Date: {report.created_at.strftime('%d %b, %Y')}")
            y -= 12
            
            c.drawString(50, y, f"Issue: {report.issue_description[:60]}...")
            y -= 20
            
            if report.image_data:
                c.setFont("Helvetica", 8)
                c.drawString(50, y, "[Image Attached]")
                y -= 50
            
            c.line(50, y, 550, y)
            y -= 15
        
        c.showPage()
        c.save()
        
        buffer.seek(0)
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=filtered_reports_{datetime.now().strftime("%Y%m%d")}.pdf'
        return response
    
    else:
        # CSV download with filtered data
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow(['ID', 'Employee ID', 'Worker', 'Department', 'Team/Area', 'Issue Description', 'Status', 'Latitude', 'Longitude', 'Created At'])
        
        for r in reports:
            writer.writerow([
                r.id, 
                r.worker.emp_id, 
                r.worker.username, 
                r.worker.department or 'N/A',
                r.worker.area or 'N/A',
                r.issue_description, 
                r.status, 
                r.latitude or 'N/A',
                r.longitude or 'N/A', 
                r.created_at.strftime('%Y-%m-%d %H:%M')
            ])
        
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=filtered_reports_{datetime.now().strftime("%Y%m%d")}.csv'
        return response

# ==================== API ROUTES ====================

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    user = User.query.filter_by(username=data.get('username')).first()
    if user and user.check_password(data.get('password')):
        login_user(user)
        return jsonify({
            'success': True, 
            'user': {
                'id': user.id, 
                'emp_id': user.emp_id,
                'username': user.username, 
                'role': user.role, 
                'department': user.department
            }
        })
    return jsonify({'success': False}), 401

@app.route('/api/signup', methods=['POST'])
def api_signup():
    data = request.get_json()
    
    if User.query.filter_by(emp_id=data.get('emp_id')).first():
        return jsonify({'success': False, 'message': 'Employee ID already exists'}), 400
    
    if User.query.filter_by(username=data.get('username')).first():
        return jsonify({'success': False, 'message': 'Username already exists'}), 400
    
    password = data.get('password')
    is_valid, error_message = validate_password_strict(password)
    if not is_valid:
        return jsonify({'success': False, 'message': error_message}), 400
    
    new_user = User(
        emp_id=data.get('emp_id'),
        username=data.get('username'), 
        role='worker', 
        department=data.get('department')
    )
    new_user.set_password(password)
    
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/reports', methods=['GET'])
@login_required
def api_get_reports():
    if current_user.role != 'admin':
        reports = Report.query.filter_by(worker_id=current_user.id).all()
    else:
        reports = Report.query.all()
    
    return jsonify({
        'success': True, 
        'reports': [{
            'id': r.id, 
            'worker_id': r.worker_id,
            'emp_id': r.worker.emp_id,
            'worker_name': r.worker.username,
            'issue_description': r.issue_description, 
            'has_image': bool(r.image_data),
            'status': r.status, 
            'created_at': r.created_at.strftime('%Y-%m-%d %H:%M')
        } for r in reports]
    })

@app.route('/api/create_report', methods=['POST'])
@login_required
def api_create_report():
    data = request.get_json()
    new_report = Report(
        worker_id=current_user.id, 
        issue_description=data.get('issue_description'), 
        status='in_progress'
    )
    db.session.add(new_report)
    db.session.commit()
    return jsonify({'success': True})

# ==================== WEB ROUTES ====================

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard' if current_user.role == 'admin' else 'worker_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and user.check_password(request.form.get('password')):
            login_user(user)
            return redirect(url_for('admin_dashboard' if user.role == 'admin' else 'worker_dashboard'))
        flash('Invalid credentials', 'error')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        emp_id = request.form.get('emp_id')
        username = request.form.get('username')
        email = request.form.get('email')
        department = request.form.get('department')
        area = request.form.get('area')
        password = request.form.get('password')
        
        if User.query.filter_by(emp_id=emp_id).first():
            flash('Employee ID already exists!', 'error')
            return render_template('signup.html')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'error')
            return render_template('signup.html')
        
        is_valid, error_message = validate_password_strict(password)
        if not is_valid:
            flash(error_message, 'error')
            return render_template('signup.html')
        
        new_user = User(
            emp_id=emp_id,
            username=username, 
            email=email,
            department=department,
            area=area,
            role='worker'
        )
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Account created! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('worker_dashboard'))
    
    from sqlalchemy import case
    from datetime import datetime, timedelta, timezone
    
    filter_date_filter = request.args.get('date_filter')
    filter_date_from = request.args.get('date_from')
    filter_date_to = request.args.get('date_to')
    filter_area = request.args.get('area')
    filter_emp_id = request.args.get('emp_id')
    
    # Use IST timezone (UTC+5:30)
    ist_offset = timedelta(hours=5, minutes=30)
    ist_timezone = timezone(ist_offset)
    ist_now = datetime.now(ist_timezone)
    today = ist_now.date()
    
    query = Report.query.join(User, Report.worker_id == User.id)
    
    if filter_date_filter == 'yesterday':
        yesterday = today - timedelta(days=1)
        from_date = datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, 0)
        to_date = datetime(today.year, today.month, today.day, 0, 0, 0)
        query = query.filter(Report.created_at >= from_date, Report.created_at < to_date)
    elif filter_date_filter == '3days':
        from_date = datetime.combine(today - timedelta(days=3), datetime.min.time())
        query = query.filter(Report.created_at >= from_date)
    elif filter_date_filter == '7days':
        from_date = datetime.combine(today - timedelta(days=7), datetime.min.time())
        query = query.filter(Report.created_at >= from_date)
    elif filter_date_filter == '1month':
        from_date = datetime.combine(today - timedelta(days=30), datetime.min.time())
        query = query.filter(Report.created_at >= from_date)
    elif filter_date_filter == 'custom':
        if filter_date_from:
            try:
                from_date = datetime.strptime(filter_date_from, '%Y-%m-%d')
                query = query.filter(Report.created_at >= from_date)
            except:
                pass
        if filter_date_to:
            try:
                to_date = datetime.strptime(filter_date_to, '%Y-%m-%d')
                to_date = to_date + timedelta(days=1)
                query = query.filter(Report.created_at < to_date)
            except:
                pass
    
    if filter_area:
        query = query.filter(User.area == filter_area)
    
    if filter_emp_id:
        query = query.filter(User.emp_id.ilike(f'%{filter_emp_id}%'))
    
    reports = query.order_by(
        case(
            (Report.status == 'pending', 1),
            (Report.status == 'in_progress', 2),
            (Report.status == 'resolved', 3),
            else_=4
        ),
        Report.created_at.desc()
    ).all()
    
    areas = [
        'Team - Pratap', 'Team - Sanga', 'Team - Phatta', 'Team - Udaj',
        'Team - Amar', 'Team - Jai Mal', 'Team - Gaura Badal', 'Team - Bappa Rawal',
        'Team - Bhamashah', 'Team - Jagat', 'Team - Karan', 'Team - Swaroop',
        'Team - Hamir', 'Team - Sajjan', 'Team - Fateh', 'Team - Sangram', 'Team - Jawan'
    ]
    
    return render_template('admin_dashboard.html', 
                        reports=reports, 
                        areas=areas,
                        filter_date_filter=filter_date_filter,
                        filter_date_from=filter_date_from,
                        filter_date_to=filter_date_to,
                        filter_area=filter_area,
                        filter_emp_id=filter_emp_id)

@app.route('/worker')
@login_required
def worker_dashboard():
    if current_user.role != 'worker':
        return redirect(url_for('admin_dashboard'))
    
    from sqlalchemy import case
    
    reports = Report.query.filter_by(worker_id=current_user.id).order_by(
        case(
            (Report.status == 'pending', 1),
            (Report.status == 'in_progress', 2),
            (Report.status == 'resolved', 3),
            else_=4
        ),
        Report.created_at.desc()
    ).all()
    
    return render_template('worker_dashboard.html', reports=reports)

@app.route('/create_report', methods=['GET', 'POST'])
@login_required
def create_report():
    if current_user.role != 'worker':
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        issue_description = request.form.get('issue_description')
        shift = request.form.get('shift')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        
        # IST timezone - DEFINE THIS FIRST
        from datetime import timezone, timedelta
        ist_offset = timedelta(hours=5, minutes=30)
        ist_timezone = timezone(ist_offset)
        
        image_data = None
        image_name = None
        image_type = None
        
        # Get current time in IST
        from datetime import datetime
        ist_now = datetime.now(ist_timezone)
        
        camera_images_data = request.form.get('camera_images')
        if camera_images_data:
            import json
            try:
                images_list = json.loads(camera_images_data)
                for idx, base64_img in enumerate(images_list):
                    if base64_img and base64_img.startswith('data:image'):
                        img_data = base64_img.split(',')[1]
                        try:
                            image_data = base64.b64decode(img_data)
                            timestamp = ist_now.timestamp()
                            image_name = f"report_{current_user.id}_{int(timestamp)}.jpg"
                            image_type = 'jpg'
                        except Exception as e:
                            print(f"Error saving camera image: {e}")
            except Exception as e:
                print(f"Error parsing camera images: {e}")
        
        file = request.files.get('camera_image')
        if file and file.filename:
            if allowed_file(file.filename):
                timestamp = ist_now.timestamp()
                image_name = secure_filename(f"{current_user.id}_{int(timestamp)}_{file.filename}")
                image_data = file.read()
                image_type = image_name.rsplit('.', 1)[1].lower() if '.' in image_name else 'jpg'
        
        new_report = Report(
            worker_id=current_user.id,
            issue_description=issue_description,
            shift=shift,
            image_data=image_data,
            image_name=image_name,
            image_type=image_type,
            latitude=float(latitude) if latitude else None,
            longitude=float(longitude) if longitude else None,
            status='in_progress',
            created_at=ist_now  # IST time - NOW IT WORKS
        )
        db.session.add(new_report)
        db.session.commit()
        
        flash('Report submitted!', 'success')
        return redirect(url_for('worker_dashboard'))
    
    return render_template('create_report.html')

@app.route('/update_report_status/<int:report_id>', methods=['POST'])
@login_required
def update_report_status(report_id):
    report = Report.query.get_or_404(report_id)
    
    if report.worker_id != current_user.id:
        flash('You can only update your own reports!', 'error')
        return redirect(url_for('worker_dashboard'))
    
    new_status = request.form.get('status')
    report.status = new_status
    db.session.commit()
    
    flash(f'Report #{report.id} status updated to {new_status}!', 'success')
    return redirect(url_for('worker_dashboard'))

# ==================== INITIALIZATION =================

def init_db():
    with app.app_context():
        db.create_all()
        
        from sqlalchemy import text
        
        try:
            result = db.session.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name='reports' AND column_name='image_data'"
            ))
            if not result.fetchone():
                db.session.execute(text("ALTER TABLE reports ADD COLUMN image_data BYTEA"))
                db.session.commit()
                print("✓ Added image_data column")
        except Exception as e:
            print(f"image_data column check: {e}")
        
        try:
            result = db.session.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name='reports' AND column_name='image_name'"
            ))
            if not result.fetchone():
                db.session.execute(text("ALTER TABLE reports ADD COLUMN image_name VARCHAR(255)"))
                db.session.commit()
                print("✓ Added image_name column")
        except Exception as e:
            print(f"image_name column check: {e}")
        
        try:
            result = db.session.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name='reports' AND column_name='image_type'"
            ))
            if not result.fetchone():
                db.session.execute(text("ALTER TABLE reports ADD COLUMN image_type VARCHAR(20)"))
                db.session.commit()
                print("✓ Added image_type column")
        except Exception as e:
            print(f"image_type column check: {e}")
        
        if not User.query.filter_by(username='admin').first():
            admin = User(
                emp_id='EMP001',
                username='admin', 
                role='admin', 
                department='Management',
                email='admin@LEAPO.com',
                area='Team - Admin'
            )
            admin.set_password('Admin@123')
            db.session.add(admin)
            
            workers_data = [
                ('EMP101', 'worker1', 'Worker@123', 'Production', 'worker1@LEAPO.com', 'Team - Pratap'),
                ('EMP102', 'worker2', 'Worker@123', 'Maintenance', 'worker2@LEAPO.com', 'Team - Sanga'),
                ('EMP103', 'worker3', 'Worker@123', 'Quality Control', 'worker3@LEAPO.com', 'Team - Phatta'),
            ]
            
            for emp_id, username, password, department, email, area in workers_data:
                worker = User(
                    emp_id=emp_id,
                    username=username, 
                    role='worker', 
                    department=department,
                    email=email,
                    area=area
                )
                worker.set_password(password)
                db.session.add(worker)
            
            db.session.commit()
            print("✓ Default users created!")
        
        print("✓ Database ready with PostgreSQL!")

# ==================== RUN APP ====================

if __name__ == '__main__':
    init_db()
    app.run(debug=False, host='0.0.0.0', port=5000) 