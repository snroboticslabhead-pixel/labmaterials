from datetime import datetime
from database import db_instance

class BaseModel:
    @staticmethod
    def dict_to_obj(data):
        """Convert MySQL dict result to object-like dictionary"""
        if not data:
            return None
        # Convert keys to be template-friendly (e.g., id to _id)
        result = {}
        for key, value in data.items():
            # Handle binary/bytes types
            if isinstance(value, bytes):
                value = value.decode('utf-8')
            result[key] = value
            # Add _id for compatibility with templates
            if key == 'id':
                result['_id'] = value
        return result

class LabModel(BaseModel):
    @staticmethod
    def get_all():
        connection = db_instance.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM labs ORDER BY name")
                labs = cursor.fetchall()
                return [BaseModel.dict_to_obj(lab) for lab in labs]
        finally:
            connection.close()
    
    @staticmethod
    def get_by_id(lab_id):
        connection = db_instance.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM labs WHERE id = %s", (lab_id,))
                lab = cursor.fetchone()
                return BaseModel.dict_to_obj(lab)
        finally:
            connection.close()
    
    @staticmethod
    def create(name, location, description):
        connection = db_instance.get_connection()
        try:
            with connection.cursor() as cursor:
                sql = """
                    INSERT INTO labs (name, location, description, created_at) 
                    VALUES (%s, %s, %s, NOW())
                """
                cursor.execute(sql, (name, location, description))
                connection.commit()
                return cursor.lastrowid
        finally:
            connection.close()
    
    @staticmethod
    def update(lab_id, name, location, description):
        connection = db_instance.get_connection()
        try:
            with connection.cursor() as cursor:
                sql = """
                    UPDATE labs 
                    SET name = %s, location = %s, description = %s 
                    WHERE id = %s
                """
                cursor.execute(sql, (name, location, description, lab_id))
                connection.commit()
        finally:
            connection.close()
    
    @staticmethod
    def delete(lab_id):
        connection = db_instance.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM labs WHERE id = %s", (lab_id,))
                connection.commit()
        finally:
            connection.close()

class CategoryModel(BaseModel):
    @staticmethod
    def get_all():
        connection = db_instance.get_connection()
        try:
            with connection.cursor() as cursor:
                sql = """
                    SELECT c.*, l.name as lab_name, 
                           (SELECT COUNT(*) FROM components WHERE category_id = c.id) as component_count,
                           (SELECT COALESCE(SUM(quantity), 0) FROM components WHERE category_id = c.id) as total_quantity
                    FROM categories c
                    LEFT JOIN labs l ON c.lab_id = l.id
                    ORDER BY l.name, c.name
                """
                cursor.execute(sql)
                categories = cursor.fetchall()
                return [BaseModel.dict_to_obj(cat) for cat in categories]
        finally:
            connection.close()
    
    @staticmethod
    def get_by_id(category_id):
        connection = db_instance.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM categories WHERE id = %s", (category_id,))
                category = cursor.fetchone()
                return BaseModel.dict_to_obj(category)
        finally:
            connection.close()
    
    @staticmethod
    def create(name, description, lab_id):
        connection = db_instance.get_connection()
        try:
            with connection.cursor() as cursor:
                sql = """
                    INSERT INTO categories (name, description, lab_id, created_at) 
                    VALUES (%s, %s, %s, NOW())
                """
                cursor.execute(sql, (name, description, lab_id))
                connection.commit()
                return cursor.lastrowid
        finally:
            connection.close()
    
    @staticmethod
    def update(category_id, name, description, lab_id):
        connection = db_instance.get_connection()
        try:
            with connection.cursor() as cursor:
                sql = """
                    UPDATE categories 
                    SET name = %s, description = %s, lab_id = %s 
                    WHERE id = %s
                """
                cursor.execute(sql, (name, description, lab_id, category_id))
                connection.commit()
        finally:
            connection.close()
    
    @staticmethod
    def delete(category_id):
        connection = db_instance.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM categories WHERE id = %s", (category_id,))
                connection.commit()
        finally:
            connection.close()

class ComponentModel(BaseModel):
    @staticmethod
    def get_all():
        connection = db_instance.get_connection()
        try:
            with connection.cursor() as cursor:
                sql = """
                    SELECT c.*, cat.name as category_name, l.name as lab_name
                    FROM components c
                    LEFT JOIN categories cat ON c.category_id = cat.id
                    LEFT JOIN labs l ON c.lab_id = l.id
                    ORDER BY c.name
                """
                cursor.execute(sql)
                components = cursor.fetchall()
                return ComponentModel.enrich_with_status(components)
        finally:
            connection.close()
    
    @staticmethod
    def get_by_lab(lab_id):
        connection = db_instance.get_connection()
        try:
            with connection.cursor() as cursor:
                sql = """
                    SELECT c.*, cat.name as category_name, l.name as lab_name
                    FROM components c
                    LEFT JOIN categories cat ON c.category_id = cat.id
                    LEFT JOIN labs l ON c.lab_id = l.id
                    WHERE c.lab_id = %s
                    ORDER BY c.name
                """
                cursor.execute(sql, (lab_id,))
                components = cursor.fetchall()
                return ComponentModel.enrich_with_status(components)
        finally:
            connection.close()
    
    @staticmethod
    def get_by_id(component_id):
        connection = db_instance.get_connection()
        try:
            with connection.cursor() as cursor:
                sql = """
                    SELECT c.*, cat.name as category_name, l.name as lab_name
                    FROM components c
                    LEFT JOIN categories cat ON c.category_id = cat.id
                    LEFT JOIN labs l ON c.lab_id = l.id
                    WHERE c.id = %s
                """
                cursor.execute(sql, (component_id,))
                component = cursor.fetchone()
                return BaseModel.dict_to_obj(component)
        finally:
            connection.close()
    
    @staticmethod
    def create(name, category_id, lab_id, quantity, min_stock_level, unit, description, component_type="Other"):
        connection = db_instance.get_connection()
        try:
            with connection.cursor() as cursor:
                sql = """
                    INSERT INTO components 
                    (name, category_id, lab_id, quantity, min_stock_level, unit, description, component_type) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (name, category_id, lab_id, quantity, min_stock_level, unit, description, component_type))
                connection.commit()
                return cursor.lastrowid
        finally:
            connection.close()
    
    @staticmethod
    def update(component_id, name, category_id, lab_id, quantity, min_stock_level, unit, description, component_type="Other"):
        connection = db_instance.get_connection()
        try:
            with connection.cursor() as cursor:
                sql = """
                    UPDATE components 
                    SET name = %s, category_id = %s, lab_id = %s, quantity = %s, 
                        min_stock_level = %s, unit = %s, description = %s, component_type = %s
                    WHERE id = %s
                """
                cursor.execute(sql, (name, category_id, lab_id, quantity, min_stock_level, unit, description, component_type, component_id))
                connection.commit()
        finally:
            connection.close()
    
    @staticmethod
    def delete(component_id):
        connection = db_instance.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM components WHERE id = %s", (component_id,))
                connection.commit()
        finally:
            connection.close()
    
    @staticmethod
    def enrich_with_status(components):
        enriched = []
        for comp in components:
            comp_dict = BaseModel.dict_to_obj(comp)
            qty = comp_dict.get('quantity', 0) or 0
            min_stock = comp_dict.get('min_stock_level', 0) or 0
            
            if qty <= 0:
                stock_state = "Out of Stock"
                stock_class = "out"
            elif qty <= min_stock:
                stock_state = "Low Stock"
                stock_class = "low"
            else:
                stock_state = "In Stock"
                stock_class = "instock"
            
            comp_dict['stock_state'] = stock_state
            comp_dict['stock_state_class'] = stock_class
            comp_dict['status_label'] = stock_state
            comp_dict['category'] = {'name': comp_dict.get('category_name', '-')}
            comp_dict['lab'] = {'name': comp_dict.get('lab_name', '-')}
            
            enriched.append(comp_dict)
        return enriched

class TransactionModel(BaseModel):
    @staticmethod
    def get_all():
        connection = db_instance.get_connection()
        try:
            with connection.cursor() as cursor:
                sql = """
                    SELECT t.*, c.name as component_name, l.name as lab_name
                    FROM transactions t
                    LEFT JOIN components c ON t.component_id = c.id
                    LEFT JOIN labs l ON t.lab_id = l.id
                    ORDER BY t.issue_date DESC
                """
                cursor.execute(sql)
                transactions = cursor.fetchall()
                return [BaseModel.dict_to_obj(txn) for txn in transactions]
        finally:
            connection.close()
    
    @staticmethod
    def get_recent(limit=5):
        connection = db_instance.get_connection()
        try:
            with connection.cursor() as cursor:
                sql = """
                    SELECT t.*, c.name as component_name
                    FROM transactions t
                    LEFT JOIN components c ON t.component_id = c.id
                    ORDER BY t.date DESC
                    LIMIT %s
                """
                cursor.execute(sql, (limit,))
                transactions = cursor.fetchall()
                return [BaseModel.dict_to_obj(txn) for txn in transactions]
        finally:
            connection.close()
    
    @staticmethod
    def create_issue(component, lab_id, campus, person_name, qty, purpose, notes):
        connection = db_instance.get_connection()
        try:
            with connection.cursor() as cursor:
                # Get current stock
                cursor.execute("SELECT quantity FROM components WHERE id = %s", (component['id'],))
                current_stock = cursor.fetchone()['quantity']
                
                if qty > current_stock:
                    raise ValueError(f"Cannot issue {qty} units. Only {current_stock} available.")
                
                quantity_after = current_stock - qty
                
                # Check for existing open transaction
                sql = """
                    SELECT * FROM transactions 
                    WHERE component_id = %s AND lab_id = %s AND campus = %s 
                    AND person_name = %s AND purpose = %s 
                    AND status IN ('Issued', 'Partially Returned')
                """
                cursor.execute(sql, (component['id'], lab_id, campus, person_name, purpose))
                existing = cursor.fetchone()
                
                if existing:
                    new_issued = existing['qty_issued'] + qty
                    pending = new_issued - existing['qty_returned']
                    status = "Issued" if existing['qty_returned'] == 0 else ("Completed" if pending <= 0 else "Partially Returned")
                    
                    update_sql = """
                        UPDATE transactions 
                        SET qty_issued = %s, pending_qty = %s, status = %s,
                            quantity_before = %s, quantity_after = %s,
                            last_action = 'issue', transaction_quantity = %s,
                            date = NOW(), last_updated = NOW()
                        WHERE id = %s
                    """
                    cursor.execute(update_sql, (new_issued, pending, status, current_stock, quantity_after, qty, existing['id']))
                else:
                    insert_sql = """
                        INSERT INTO transactions 
                        (component_id, lab_id, campus, person_name, purpose, qty_issued, 
                         qty_returned, pending_qty, status, issue_date, date, quantity_before,
                         quantity_after, transaction_quantity, last_action, notes)
                        VALUES (%s, %s, %s, %s, %s, %s, 0, %s, 'Issued', NOW(), NOW(), %s, %s, %s, 'issue', %s)
                    """
                    cursor.execute(insert_sql, (component['id'], lab_id, campus, person_name, purpose, qty, qty, current_stock, quantity_after, qty, notes))
                
                # Update component stock
                cursor.execute("UPDATE components SET quantity = %s WHERE id = %s", (quantity_after, component['id']))
                
                connection.commit()
        finally:
            connection.close()
    
    @staticmethod
    def add_return(component, lab_id, campus, person_name, qty, purpose, notes):
        connection = db_instance.get_connection()
        try:
            with connection.cursor() as cursor:
                # Get current stock
                cursor.execute("SELECT quantity FROM components WHERE id = %s", (component['id'],))
                current_stock = cursor.fetchone()['quantity']
                
                # Find existing transaction
                sql = """
                    SELECT * FROM transactions 
                    WHERE component_id = %s AND lab_id = %s AND campus = %s 
                    AND person_name = %s AND purpose = %s 
                    AND status IN ('Issued', 'Partially Returned')
                """
                cursor.execute(sql, (component['id'], lab_id, campus, person_name, purpose))
                existing = cursor.fetchone()
                
                if not existing:
                    raise ValueError("No matching issued transaction found.")
                
                pending = existing['pending_qty']
                if pending <= 0:
                    raise ValueError("No pending quantity left to return.")
                
                if qty > pending:
                    raise ValueError(f"Return quantity ({qty}) cannot exceed pending quantity ({pending}).")
                
                new_returned = existing['qty_returned'] + qty
                new_pending = existing['qty_issued'] - new_returned
                status = "Completed" if new_pending <= 0 else "Partially Returned"
                quantity_after = current_stock + qty
                
                update_sql = """
                    UPDATE transactions 
                    SET qty_returned = %s, pending_qty = %s, status = %s,
                        quantity_before = %s, quantity_after = %s,
                        last_action = 'return', transaction_quantity = %s,
                        date = NOW(), last_updated = NOW(),
                        notes = CONCAT(COALESCE(notes, ''), %s)
                    WHERE id = %s
                """
                note_append = f"\nReturn: {notes}" if notes else ""
                cursor.execute(update_sql, (new_returned, new_pending, status, current_stock, quantity_after, qty, note_append, existing['id']))
                
                # Update component stock
                cursor.execute("UPDATE components SET quantity = %s WHERE id = %s", (quantity_after, component['id']))
                
                connection.commit()
        finally:
            connection.close()
    
    @staticmethod
    def get_by_id(transaction_id):
        connection = db_instance.get_connection()
        try:
            with connection.cursor() as cursor:
                sql = """
                    SELECT t.*, c.name as component_name, l.name as lab_name
                    FROM transactions t
                    LEFT JOIN components c ON t.component_id = c.id
                    LEFT JOIN labs l ON t.lab_id = l.id
                    WHERE t.id = %s
                """
                cursor.execute(sql, (transaction_id,))
                txn = cursor.fetchone()
                return BaseModel.dict_to_obj(txn)
        finally:
            connection.close()

class UserModel(BaseModel):
    @staticmethod
    def authenticate(username, password):
        connection = db_instance.get_connection()
        try:
            with connection.cursor() as cursor:
                # For simplicity, using plain text comparison
                # In production, use password hashing
                sql = "SELECT * FROM users WHERE username = %s AND password = %s"
                cursor.execute(sql, (username, password))
                user = cursor.fetchone()
                return BaseModel.dict_to_obj(user)
        finally:
            connection.close()
    
    @staticmethod
    def get_by_username(username):
        connection = db_instance.get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
                user = cursor.fetchone()
                return BaseModel.dict_to_obj(user)
        finally:
            connection.close()
