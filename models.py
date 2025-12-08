import mysql.connector
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# Helper to get Dictionary Cursors (makes rows look like Python Dicts)
def get_db_connection(config):
    conn = mysql.connector.connect(
        host=config.MYSQL_HOST,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        database=config.MYSQL_DB
    )
    return conn

class Schema:
    @staticmethod
    def create_tables(config):
        conn = get_db_connection(config)
        cursor = conn.cursor()
        
        # 1. Users Table (From your prompt)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(80) UNIQUE NOT NULL,
                email VARCHAR(120) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                role ENUM('admin', 'trainer') NOT NULL DEFAULT 'admin',
                lab_id INT,
                lab_name VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 2. Labs Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS labs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                location VARCHAR(100),
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 3. Categories Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                lab_id INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lab_id) REFERENCES labs(id) ON DELETE SET NULL
            )
        ''')

        # 4. Components Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS components (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(150) NOT NULL,
                category_id INT,
                lab_id INT,
                quantity INT DEFAULT 0,
                min_stock_level INT DEFAULT 0,
                unit VARCHAR(50),
                description TEXT,
                component_type VARCHAR(50) DEFAULT 'Other',
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL,
                FOREIGN KEY (lab_id) REFERENCES labs(id) ON DELETE SET NULL
            )
        ''')

        # 5. Transactions Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                component_id INT NOT NULL,
                lab_id INT,
                campus VARCHAR(100),
                person_name VARCHAR(100),
                purpose TEXT,
                qty_issued INT DEFAULT 0,
                qty_returned INT DEFAULT 0,
                pending_qty INT DEFAULT 0,
                status VARCHAR(50), 
                notes TEXT,
                issue_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE CASCADE,
                FOREIGN KEY (lab_id) REFERENCES labs(id) ON DELETE SET NULL
            )
        ''')
        
        # Create a default admin user if none exists
        cursor.execute("SELECT * FROM users WHERE username = 'admin'")
        if not cursor.fetchone():
            hashed_pw = generate_password_hash("admin123")
            cursor.execute('''
                INSERT INTO users (username, email, password, role) 
                VALUES (%s, %s, %s, 'admin')
            ''', ('admin', 'admin@example.com', hashed_pw))
            
        conn.commit()
        cursor.close()
        conn.close()

class LabModel:
    @staticmethod
    def get_all(cursor):
        cursor.execute("SELECT * FROM labs ORDER BY name")
        return cursor.fetchall()

    @staticmethod
    def get_by_id(cursor, lab_id):
        cursor.execute("SELECT * FROM labs WHERE id = %s", (lab_id,))
        return cursor.fetchone()

    @staticmethod
    def create(cursor, name, location, description):
        cursor.execute(
            "INSERT INTO labs (name, location, description) VALUES (%s, %s, %s)",
            (name, location, description)
        )

    @staticmethod
    def update(cursor, lab_id, name, location, description):
        cursor.execute(
            "UPDATE labs SET name=%s, location=%s, description=%s WHERE id=%s",
            (name, location, description, lab_id)
        )

    @staticmethod
    def delete(cursor, lab_id):
        cursor.execute("DELETE FROM labs WHERE id = %s", (lab_id,))

class CategoryModel:
    @staticmethod
    def get_all(cursor):
        # Join with Labs to get lab name, count components
        query = """
            SELECT c.*, l.name as lab_name,
            (SELECT COUNT(*) FROM components comp WHERE comp.category_id = c.id) as component_count,
            (SELECT COALESCE(SUM(quantity),0) FROM components comp WHERE comp.category_id = c.id) as total_quantity
            FROM categories c
            LEFT JOIN labs l ON c.lab_id = l.id
            ORDER BY c.name
        """
        cursor.execute(query)
        return cursor.fetchall()

    @staticmethod
    def get_by_id(cursor, cat_id):
        cursor.execute("SELECT * FROM categories WHERE id = %s", (cat_id,))
        return cursor.fetchone()

    @staticmethod
    def create(cursor, name, description, lab_id):
        cursor.execute(
            "INSERT INTO categories (name, description, lab_id) VALUES (%s, %s, %s)",
            (name, description, lab_id or None)
        )

    @staticmethod
    def update(cursor, cat_id, name, description, lab_id):
        cursor.execute(
            "UPDATE categories SET name=%s, description=%s, lab_id=%s WHERE id=%s",
            (name, description, lab_id or None, cat_id)
        )

    @staticmethod
    def delete(cursor, cat_id):
        cursor.execute("DELETE FROM categories WHERE id = %s", (cat_id,))

class ComponentModel:
    @staticmethod
    def get_all(cursor, lab_id=None):
        base_query = """
            SELECT c.*, cat.name as category_name, l.name as lab_name 
            FROM components c
            LEFT JOIN categories cat ON c.category_id = cat.id
            LEFT JOIN labs l ON c.lab_id = l.id
        """
        if lab_id:
            base_query += " WHERE c.lab_id = %s"
            base_query += " ORDER BY c.name"
            cursor.execute(base_query, (lab_id,))
        else:
            base_query += " ORDER BY c.name"
            cursor.execute(base_query)
        return cursor.fetchall()

    @staticmethod
    def get_by_id(cursor, comp_id):
        cursor.execute("SELECT * FROM components WHERE id = %s", (comp_id,))
        return cursor.fetchone()

    @staticmethod
    def create(cursor, name, category_id, lab_id, quantity, min_stock, unit, desc, c_type):
        cursor.execute("""
            INSERT INTO components 
            (name, category_id, lab_id, quantity, min_stock_level, unit, description, component_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (name, category_id, lab_id, quantity, min_stock, unit, desc, c_type))

    @staticmethod
    def update(cursor, comp_id, name, category_id, lab_id, quantity, min_stock, unit, desc, c_type):
        cursor.execute("""
            UPDATE components SET 
            name=%s, category_id=%s, lab_id=%s, quantity=%s, min_stock_level=%s, 
            unit=%s, description=%s, component_type=%s
            WHERE id=%s
        """, (name, category_id, lab_id, quantity, min_stock, unit, desc, c_type, comp_id))

    @staticmethod
    def delete(cursor, comp_id):
        cursor.execute("DELETE FROM components WHERE id=%s", (comp_id,))

    @staticmethod
    def enrich_with_status(components):
        for c in components:
            qty = c.get('quantity', 0)
            min_stock = c.get('min_stock_level', 0)
            if qty <= 0:
                c['stock_state'] = "Out of Stock"
                c['stock_class'] = "out"
            elif qty <= min_stock:
                c['stock_state'] = "Low Stock"
                c['stock_class'] = "low"
            else:
                c['stock_state'] = "In Stock"
                c['stock_class'] = "instock"
        return components

class TransactionModel:
    @staticmethod
    def get_all(cursor):
        query = """
            SELECT t.*, c.name as component_name, l.name as lab_name
            FROM transactions t
            LEFT JOIN components c ON t.component_id = c.id
            LEFT JOIN labs l ON t.lab_id = l.id
            ORDER BY t.issue_date DESC
        """
        cursor.execute(query)
        return cursor.fetchall()

    @staticmethod
    def get_recent(cursor, limit=5):
        query = """
            SELECT t.*, c.name as component_name 
            FROM transactions t
            LEFT JOIN components c ON t.component_id = c.id
            ORDER BY t.issue_date DESC LIMIT %s
        """
        cursor.execute(query, (limit,))
        return cursor.fetchall()

    @staticmethod
    def create_issue(cursor, comp_id, lab_id, campus, person, qty, purpose, notes):
        # 1. Check stock
        cursor.execute("SELECT quantity FROM components WHERE id=%s", (comp_id,))
        row = cursor.fetchone()
        current_stock = row['quantity'] if row else 0
        
        if qty > current_stock:
            raise ValueError(f"Insufficient stock. Available: {current_stock}")
            
        # 2. Check existing open transaction
        cursor.execute("""
            SELECT * FROM transactions 
            WHERE component_id=%s AND person_name=%s AND status IN ('Issued', 'Partially Returned')
        """, (comp_id, person))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing
            new_issued = existing['qty_issued'] + qty
            new_pending = new_issued - existing['qty_returned']
            status = 'Issued' if existing['qty_returned'] == 0 else 'Partially Returned'
            
            cursor.execute("""
                UPDATE transactions SET qty_issued=%s, pending_qty=%s, status=%s, 
                notes=CONCAT(notes, '\n', %s), last_updated=NOW()
                WHERE id=%s
            """, (new_issued, new_pending, status, f"Added {qty}: {notes}", existing['id']))
        else:
            # Create new
            cursor.execute("""
                INSERT INTO transactions 
                (component_id, lab_id, campus, person_name, purpose, qty_issued, qty_returned, pending_qty, status, notes)
                VALUES (%s, %s, %s, %s, %s, %s, 0, %s, 'Issued', %s)
            """, (comp_id, lab_id, campus, person, purpose, qty, qty, notes))
            
        # 3. Deduct Stock
        cursor.execute("UPDATE components SET quantity = quantity - %s WHERE id=%s", (qty, comp_id))

    @staticmethod
    def add_return(cursor, txn_id, return_qty, notes):
        cursor.execute("SELECT * FROM transactions WHERE id=%s", (txn_id,))
        txn = cursor.fetchone()
        if not txn:
            raise ValueError("Transaction not found")
            
        if return_qty > txn['pending_qty']:
            raise ValueError(f"Return quantity ({return_qty}) cannot exceed pending ({txn['pending_qty']})")
            
        new_returned = txn['qty_returned'] + return_qty
        new_pending = txn['qty_issued'] - new_returned
        status = 'Completed' if new_pending == 0 else 'Partially Returned'
        
        cursor.execute("""
            UPDATE transactions SET qty_returned=%s, pending_qty=%s, status=%s, 
            notes=CONCAT(notes, '\nReturn: ', %s), last_updated=NOW()
            WHERE id=%s
        """, (new_returned, new_pending, status, notes, txn_id))
        
        # Add Stock Back
        cursor.execute("UPDATE components SET quantity = quantity + %s WHERE id=%s", 
                       (return_qty, txn['component_id']))
