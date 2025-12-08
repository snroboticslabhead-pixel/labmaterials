from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, session, g
)
import mysql.connector
from functools import wraps
from werkzeug.security import check_password_hash

from config import Config
from models import (
    Schema, LabModel, CategoryModel, ComponentModel, TransactionModel
)

app = Flask(__name__)
app.config.from_object(Config)

# --- Database Connection Management ---
def get_db():
    if 'db' not in g:
        g.db = mysql.connector.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DB']
        )
        g.cursor = g.db.cursor(dictionary=True) # Important: Returns rows as dicts
    return g.db, g.cursor

@app.teardown_appcontext
def teardown_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# Initialize DB (Create Tables) on first run
with app.app_context():
    try:
        Schema.create_tables(Config)
    except Exception as e:
        print(f"DB Init Error (Ignorable if tables exist): {e}")

# --- Authentication ---

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/login", methods=["GET", "POST"])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        db, cursor = get_db()
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()

        # Check hash, OR plain text if you inserted manually without hashing
        if user and (check_password_hash(user['password'], password) or user['password'] == password):
            session['user_id'] = user['id']
            session['user'] = user['username']
            session['role'] = user['role']
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid username or password.", "danger")
            
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

# --- Dashboard Helper ---
def get_dashboard_stats():
    db, cursor = get_db()
    
    cursor.execute("SELECT COUNT(*) as c FROM components")
    total_components = cursor.fetchone()['c']
    
    cursor.execute("SELECT COUNT(*) as c FROM transactions")
    total_transactions = cursor.fetchone()['c']
    
    cursor.execute("SELECT COUNT(*) as c FROM labs")
    total_labs = cursor.fetchone()['c']
    
    cursor.execute("SELECT COUNT(*) as c FROM categories")
    total_categories = cursor.fetchone()['c']
    
    cursor.execute("SELECT COUNT(*) as c FROM transactions WHERE status IN ('Issued', 'Partially Returned')")
    pending_returns = cursor.fetchone()['c']
    
    cursor.execute("SELECT COUNT(*) as c FROM components WHERE quantity <= min_stock_level")
    low_stock = cursor.fetchone()['c']
    
    cursor.execute("SELECT COUNT(*) as c FROM components WHERE quantity <= 0")
    out_of_stock = cursor.fetchone()['c']
    
    # Lab Stats
    cursor.execute("""
        SELECT l.name as lab_name, COUNT(c.id) as component_count 
        FROM labs l LEFT JOIN components c ON l.id = c.lab_id 
        GROUP BY l.id, l.name
    """)
    lab_stats = cursor.fetchall()
    
    recent_transactions = TransactionModel.get_recent(cursor)
    
    return {
        "total_components": total_components,
        "total_transactions": total_transactions,
        "total_labs": total_labs,
        "total_categories": total_categories,
        "pending_returns": pending_returns,
        "low_stock_components": low_stock,
        "out_of_stock_components": out_of_stock,
        "lab_stats": lab_stats,
        "recent_transactions": recent_transactions
    }

# --- Routes ---

@app.route("/")
@login_required
def index():
    stats = get_dashboard_stats()
    
    # Chart Data
    db, cursor = get_db()
    cursor.execute("SELECT status, COUNT(*) as count FROM transactions GROUP BY status")
    rows = cursor.fetchall()
    
    transaction_types = [r['status'] for r in rows]
    transaction_counts = [r['count'] for r in rows]
    
    return render_template(
        "index.html",
        stats=stats,
        transaction_types=transaction_types,
        transaction_counts=transaction_counts
    )

# --- Labs CRUD ---
@app.route("/labs", methods=["GET", "POST"])
@login_required
def labs():
    db, cursor = get_db()
    if request.method == "POST":
        LabModel.create(cursor, 
            request.form.get("name"), 
            request.form.get("location"), 
            request.form.get("description")
        )
        db.commit()
        flash("Lab added.", "success")
        return redirect(url_for("labs"))
        
    return render_template("labs.html", labs=LabModel.get_all(cursor))

@app.route("/labs/<int:lab_id>/edit", methods=["GET", "POST"])
@login_required
def edit_lab(lab_id):
    db, cursor = get_db()
    lab = LabModel.get_by_id(cursor, lab_id)
    if not lab:
        return redirect(url_for("labs"))
        
    if request.method == "POST":
        LabModel.update(cursor, lab_id,
            request.form.get("name"), 
            request.form.get("location"), 
            request.form.get("description")
        )
        db.commit()
        flash("Lab updated.", "success")
        return redirect(url_for("labs"))
        
    return render_template("edit_lab.html", lab=lab)

@app.route("/labs/<int:lab_id>/delete", methods=["POST"])
@login_required
def delete_lab(lab_id):
    db, cursor = get_db()
    LabModel.delete(cursor, lab_id)
    db.commit()
    flash("Lab deleted.", "info")
    return redirect(url_for("labs"))

# --- Categories CRUD ---
@app.route("/categories", methods=["GET", "POST"])
@login_required
def categories():
    db, cursor = get_db()
    if request.method == "POST":
        CategoryModel.create(cursor,
            request.form.get("name"),
            request.form.get("description"),
            request.form.get("lab_id")
        )
        db.commit()
        flash("Category added.", "success")
        return redirect(url_for("categories"))
        
    return render_template("categories.html", 
        categories=CategoryModel.get_all(cursor),
        labs=LabModel.get_all(cursor)
    )

@app.route("/categories/<int:cat_id>/delete", methods=["POST"])
@login_required
def delete_category(cat_id):
    db, cursor = get_db()
    CategoryModel.delete(cursor, cat_id)
    db.commit()
    return redirect(url_for("categories"))

# --- Components CRUD ---
@app.route("/components")
@login_required
def components():
    db, cursor = get_db()
    comps = ComponentModel.get_all(cursor)
    comps = ComponentModel.enrich_with_status(comps)
    return render_template("components.html", components=comps)

@app.route("/components/add", methods=["GET", "POST"])
@login_required
def add_component():
    db, cursor = get_db()
    if request.method == "POST":
        ComponentModel.create(cursor,
            request.form.get("name"),
            request.form.get("category_id"),
            request.form.get("lab_id"),
            int(request.form.get("quantity") or 0),
            int(request.form.get("min_stock_level") or 0),
            request.form.get("unit"),
            request.form.get("description"),
            request.form.get("component_type")
        )
        db.commit()
        flash("Component added.", "success")
        return redirect(url_for("components"))
        
    return render_template("add_component.html", 
        labs=LabModel.get_all(cursor), 
        categories=CategoryModel.get_all(cursor)
    )

@app.route("/components/<int:comp_id>/edit", methods=["GET", "POST"])
@login_required
def edit_component(comp_id):
    db, cursor = get_db()
    comp = ComponentModel.get_by_id(cursor, comp_id)
    
    if request.method == "POST":
        ComponentModel.update(cursor, comp_id,
            request.form.get("name"),
            request.form.get("category_id"),
            request.form.get("lab_id"),
            int(request.form.get("quantity") or 0),
            int(request.form.get("min_stock_level") or 0),
            request.form.get("unit"),
            request.form.get("description"),
            request.form.get("component_type")
        )
        db.commit()
        flash("Component updated.", "success")
        return redirect(url_for("components"))
        
    return render_template("edit_component.html", 
        component=comp,
        labs=LabModel.get_all(cursor), 
        categories=CategoryModel.get_all(cursor)
    )

@app.route("/components/<int:comp_id>/delete", methods=["POST"])
@login_required
def delete_component(comp_id):
    db, cursor = get_db()
    ComponentModel.delete(cursor, comp_id)
    db.commit()
    flash("Component deleted.", "info")
    return redirect(url_for("components"))

# --- Transactions ---
@app.route("/transactions")
@login_required
def transactions():
    db, cursor = get_db()
    txns = TransactionModel.get_all(cursor)
    
    # Status Counts
    cursor.execute("SELECT status, COUNT(*) as c FROM transactions GROUP BY status")
    status_counts = {row['status']: row['c'] for row in cursor.fetchall()}
    
    return render_template("transactions.html", transactions=txns, status_counts=status_counts)

@app.route("/transactions/add", methods=["GET", "POST"])
@login_required
def add_transaction():
    db, cursor = get_db()
    comps = ComponentModel.get_all(cursor)
    labs = LabModel.get_all(cursor)
    
    if request.method == "POST":
        try:
            TransactionModel.create_issue(cursor,
                int(request.form.get("component_id")),
                request.form.get("from_lab_id"),
                request.form.get("from_campus"),
                request.form.get("person_name"),
                int(request.form.get("transaction_quantity")),
                request.form.get("purpose"),
                request.form.get("notes")
            )
            db.commit()
            flash("Transaction recorded.", "success")
            return redirect(url_for("transactions"))
        except ValueError as e:
            flash(str(e), "danger")
            
    return render_template("add_transaction.html", components=comps, labs=labs)

@app.route("/transactions/<int:txn_id>/edit", methods=["GET", "POST"])
@login_required
def edit_transaction(txn_id):
    db, cursor = get_db()
    cursor.execute("SELECT * FROM transactions WHERE id=%s", (txn_id,))
    txn = cursor.fetchone()
    if not txn: return redirect(url_for("transactions"))
    
    comp = ComponentModel.get_by_id(cursor, txn['component_id'])
    
    if request.method == "POST":
        try:
            TransactionModel.add_return(cursor, txn_id,
                int(request.form.get("return_now") or 0),
                request.form.get("notes")
            )
            db.commit()
            flash("Return recorded.", "success")
            return redirect(url_for("transactions"))
        except ValueError as e:
            flash(str(e), "danger")
            
    return render_template("edit_transaction.html", txn=txn, component=comp)

# --- Reports ---
@app.route("/reports")
@login_required
def reports():
    db, cursor = get_db()
    
    cursor.execute("""
        SELECT l.name as _id, COUNT(*) as count 
        FROM components c JOIN labs l ON c.lab_id = l.id 
        GROUP BY l.name
    """)
    by_lab = cursor.fetchall()
    
    cursor.execute("""
        SELECT cat.name as _id, COUNT(*) as count 
        FROM components c JOIN categories cat ON c.category_id = cat.id 
        GROUP BY cat.name
    """)
    by_cat = cursor.fetchall()
    
    cursor.execute("SELECT * FROM components WHERE quantity <= min_stock_level")
    low_stock = cursor.fetchall()
    
    return render_template("reports.html", 
        components_by_lab=by_lab,
        components_by_category=by_cat,
        low_stock_components=low_stock
    )

if __name__ == "__main__":
    app.run(debug=True)
