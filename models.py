from datetime import datetime
from zoneinfo import ZoneInfo
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()
IST = ZoneInfo("Asia/Kolkata")  # Indian time

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum('admin', 'trainer'), nullable=False, default='admin')
    lab_id = db.Column(db.Integer, db.ForeignKey('labs.id'), nullable=True)
    lab_name = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.TIMESTAMP, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password, password)

class Lab(db.Model):
    __tablename__ = 'labs'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    location = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.TIMESTAMP, default=datetime.utcnow)
    
    components = db.relationship('Component', backref='lab', lazy=True)
    categories = db.relationship('Category', backref='lab', lazy=True)
    transactions = db.relationship('Transaction', backref='lab', lazy=True)

class Category(db.Model):
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    lab_id = db.Column(db.Integer, db.ForeignKey('labs.id'), nullable=False)
    created_at = db.Column(db.TIMESTAMP, default=datetime.utcnow)
    
    components = db.relationship('Component', backref='category', lazy=True)

class Component(db.Model):
    __tablename__ = 'components'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    lab_id = db.Column(db.Integer, db.ForeignKey('labs.id'), nullable=False)
    quantity = db.Column(db.Integer, default=0)
    min_stock_level = db.Column(db.Integer, default=0)
    unit = db.Column(db.String(50), nullable=True)
    description = db.Column(db.Text, nullable=True)
    component_type = db.Column(db.String(100), default='Other')
    date_added = db.Column(db.TIMESTAMP, default=datetime.utcnow)
    last_updated = db.Column(db.TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    transactions = db.relationship('Transaction', backref='component', lazy=True)

class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    component_id = db.Column(db.Integer, db.ForeignKey('components.id'), nullable=False)
    lab_id = db.Column(db.Integer, db.ForeignKey('labs.id'), nullable=False)
    campus = db.Column(db.String(255), nullable=True)
    person_name = db.Column(db.String(255), nullable=False)
    purpose = db.Column(db.String(255), nullable=False)
    qty_issued = db.Column(db.Integer, default=0)
    qty_returned = db.Column(db.Integer, default=0)
    pending_qty = db.Column(db.Integer, default=0)
    status = db.Column(db.Enum('Issued', 'Partially Returned', 'Completed'), nullable=False)
    issue_date = db.Column(db.TIMESTAMP, default=datetime.utcnow)
    date = db.Column(db.TIMESTAMP, default=datetime.utcnow)  # Last action date
    quantity_before = db.Column(db.Integer, nullable=True)
    quantity_after = db.Column(db.Integer, nullable=True)
    transaction_quantity = db.Column(db.Integer, nullable=True)
    last_action = db.Column(db.Enum('issue', 'return'), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    last_updated = db.Column(db.TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
