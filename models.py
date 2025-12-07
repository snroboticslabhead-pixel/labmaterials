from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pytz

db = SQLAlchemy()

IST = pytz.timezone('Asia/Kolkata')

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum('admin', 'trainer'), nullable=False)
    lab_id = db.Column(db.Integer, db.ForeignKey('labs.id'))
    lab_name = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'lab_id': self.lab_id,
            'lab_name': self.lab_name
        }

class Lab(db.Model):
    __tablename__ = 'labs'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    location = db.Column(db.String(255))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(IST))
    
    categories = db.relationship('Category', backref='lab', lazy=True, cascade='all, delete-orphan')
    components = db.relationship('Component', backref='lab', lazy=True, cascade='all, delete-orphan')
    transactions = db.relationship('Transaction', backref='lab', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'location': self.location,
            'description': self.description,
            'created_at': self.created_at
        }

class Category(db.Model):
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    lab_id = db.Column(db.Integer, db.ForeignKey('labs.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(IST))
    
    components = db.relationship('Component', backref='category', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'lab_id': self.lab_id,
            'created_at': self.created_at
        }

class Component(db.Model):
    __tablename__ = 'components'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    lab_id = db.Column(db.Integer, db.ForeignKey('labs.id'), nullable=False)
    quantity = db.Column(db.Integer, default=0)
    min_stock_level = db.Column(db.Integer, default=0)
    unit = db.Column(db.String(50))
    description = db.Column(db.Text)
    component_type = db.Column(db.String(100), default='Other')
    date_added = db.Column(db.DateTime, default=lambda: datetime.now(IST))
    last_updated = db.Column(db.DateTime, default=lambda: datetime.now(IST), onupdate=lambda: datetime.now(IST))
    
    transactions = db.relationship('Transaction', backref='component', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category_id': self.category_id,
            'lab_id': self.lab_id,
            'quantity': self.quantity,
            'min_stock_level': self.min_stock_level,
            'unit': self.unit,
            'description': self.description,
            'component_type': self.component_type,
            'date_added': self.date_added,
            'last_updated': self.last_updated
        }

class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    component_id = db.Column(db.Integer, db.ForeignKey('components.id'), nullable=False)
    lab_id = db.Column(db.Integer, db.ForeignKey('labs.id'), nullable=False)
    campus = db.Column(db.String(255))
    person_name = db.Column(db.String(255), nullable=False)
    purpose = db.Column(db.String(500), nullable=False)
    qty_issued = db.Column(db.Integer, default=0)
    qty_returned = db.Column(db.Integer, default=0)
    pending_qty = db.Column(db.Integer, default=0)
    status = db.Column(db.Enum('Issued', 'Partially Returned', 'Completed'), default='Issued')
    issue_date = db.Column(db.DateTime, default=lambda: datetime.now(IST))
    date = db.Column(db.DateTime, default=lambda: datetime.now(IST))  # Last action date
    quantity_before = db.Column(db.Integer)
    quantity_after = db.Column(db.Integer)
    transaction_quantity = db.Column(db.Integer)  # Quantity of last action
    last_action = db.Column(db.Enum('issue', 'return'), default='issue')
    notes = db.Column(db.Text)
    last_updated = db.Column(db.DateTime, default=lambda: datetime.now(IST), onupdate=lambda: datetime.now(IST))
    
    def to_dict(self):
        return {
            'id': self.id,
            'component_id': self.component_id,
            'lab_id': self.lab_id,
            'campus': self.campus,
            'person_name': self.person_name,
            'purpose': self.purpose,
            'qty_issued': self.qty_issued,
            'qty_returned': self.qty_returned,
            'pending_qty': self.pending_qty,
            'status': self.status,
            'issue_date': self.issue_date,
            'date': self.date,
            'quantity_before': self.quantity_before,
            'quantity_after': self.quantity_after,
            'transaction_quantity': self.transaction_quantity,
            'last_action': self.last_action,
            'notes': self.notes,
            'last_updated': self.last_updated
        }
