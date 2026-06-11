from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import re
import random
from datetime import timedelta as td

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    emp_id = db.Column(db.String(50), unique=True, nullable=False)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(500), nullable=False)
    role = db.Column(db.String(20), nullable=False)  
    department = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(150), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    area = db.Column(db.String(100), nullable=True)  
    
    # OTP fields
    otp_code = db.Column(db.String(6), nullable=True)
    otp_expiry = db.Column(db.DateTime, nullable=True)
    
    def set_password(self, password):
        if not self.validate_password(password):
            raise ValueError("Password does not meet requirements")
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def generate_otp(self):
        """Generate 6-digit OTP"""
        self.otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        self.otp_expiry = datetime.utcnow() + td(minutes=10)
        return self.otp_code
    
    def verify_otp(self, otp):
        """Verify OTP and clear if valid"""
        if self.otp_code and self.otp_expiry:
            if self.otp_code == otp and self.otp_expiry > datetime.utcnow():
                self.otp_code = None
                self.otp_expiry = None
                return True
        return False
    
    @staticmethod
    def validate_password(password):
        if len(password) < 8:
            return False
        if not re.search(r'[A-Z]', password):
            return False
        if not re.search(r'[a-z]', password):
            return False
        if not re.search(r'\d', password):
            return False
        if not re.search(r'[!@#$%^&*()_+\-=\$\${};:\'",.<>?/\\|`~]', password):
            return False
        return True
    
    @staticmethod
    def get_password_requirements():
        return """Password must:
        - Be at least 8 characters
        - Have uppercase (A-Z)
        - Have lowercase (a-z)
        - Have digit (0-9)
        - Have special character (!@#$%^&*)"""
    
    def __repr__(self):
        return f'<User {self.username}>'


class Report(db.Model):
    __tablename__ = 'reports'
    
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    issue_description = db.Column(db.Text, nullable=False)
    pending_reason = db.Column(db.Text, nullable=True)

    
    # NEW - Image stored in PostgreSQL (BYTEA)
    image_data = db.Column(db.LargeBinary(), nullable=True)  # Actual image data
    image_name = db.Column(db.String(255), nullable=True)  # Original filename
    image_type = db.Column(db.String(20), nullable=True)  # File type (jpg, png, gif)
    
    # Keep old column for backward compatibility (will phase out)
    image_path = db.Column(db.String(1000), nullable=True)
    
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone(timedelta(hours=5, minutes=30))))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    shift = db.Column(db.String(20), nullable=True)  

    team_area = db.Column(db.String(100))
    
    worker = db.relationship('User', backref='reports')
    
    @property
    def has_image(self):
        """Check if report has an image (either new or old)"""
        return bool(self.image_data or self.image_path)
    
    @property
    def image_display_path(self):
        """Get image path for templates - prefers new database storage"""
        if self.image_data:
            return f'/image/{self.id}'
        elif self.image_path:
            return f'/static/uploads/{self.image_path}'
        return None
    
    @property
    def image_thumb_path(self):
        """Get thumbnail path for templates - prefers new database storage"""
        if self.image_data:
            return f'/image_thumb/{self.id}'
        elif self.image_path:
            return f'/static/uploads/{self.image_path}'
        return None
    
    def __repr__(self):
        return f'<Report {self.id}>'