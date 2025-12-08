from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, session
)
from functools import wraps
from config import Config
from database import db_instance
from models import (
    LabModel, CategoryModel, ComponentModel, 
    TransactionModel, UserModel
)

app = Flask(__name__)
app.config.from_object(Config)

# Initialize database
db_instance.init_db()

# ---------------------- Authentication Logic ---------------------- #

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/login", methods=["GET", "POST"])
def login():
    if 'user' in session:
        return redirect(url_for('index'))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = UserModel.authenticate(username, password)
        
        if user:
            session['user'] = user['username']
            session['role'] = user['role']
            flash("Welcome back!", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid username or password.", "danger")
            
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop('user', None)
    session.pop('role', None)
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

# ---------------------- Helper: dashboard stats ---------------------- #
def get_dashboard_stats():
    connection = db_instance.get_connection()
    try:
        with connection.cursor() as cursor:
            # Total components
            cursor.execute("SELECT COUNT(*) as count FROM components")
            total_components = cursor.fetchone()['count']
            
            # Total transactions
            cursor.execute("SELECT COUNT(*) as count FROM transactions")
            total_transactions = cursor.fetchone()['count']
            
            # Total labs
            cursor.execute("SELECT COUNT(*) as count FROM labs")
            total_labs = cursor.fetchone()['count']
            
            # Total categories
            cursor.execute("SELECT COUNT(*) as count FROM categories")
            total_categories = cursor.fetchone()['count']
            
            # Pending returns
            cursor.execute("SELECT COUNT(*) as count FROM transactions WHERE status IN ('Issued', 'Partially Returned')")
            pending_returns = cursor.fetchone()['count']
            
            # Low stock components
            cursor.execute("SELECT COUNT(*) as count FROM components WHERE quantity <= min_stock_level AND quantity > 0")
            low_stock_components = cursor.fetchone()['count']
            
            # Out of stock components
            cursor.execute("SELECT COUNT(*) as count FROM components WHERE quantity <= 0")
            out_of_stock_components = cursor.fetchone()['count']
            
            # Lab stats
            cursor.execute("""
                SELECT l.name as lab_name, COUNT(c.id) as component_count
                FROM labs l
                LEFT JOIN components c ON l.id = c.lab_id
                GROUP BY l.id, l.name
                ORDER BY l.name
            """)
            lab_stats = cursor.fetchall()
            
            # Recent transactions
            recent_transactions = TransactionModel.get_recent(limit=5)
            
            return {
                "total_components": total_components,
                "total_transactions": total_transactions,
                "total_labs": total_labs,
                "total_categories": total_categories,
                "pending_returns": pending_returns,
                "low_stock_components": low_stock_components,
                "out_of_stock_components": out_of_stock_components,
                "lab_stats": lab_stats,
                "recent_transactions": recent_transactions
            }
    finally:
        connection.close()

# ---------------------- Routes (Protected) ---------------------- #

@app.route("/")
@login_required
def index():
    stats = get_dashboard_stats()

    # Transaction counts by STATUS
    connection = db_instance.get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT status, COUNT(*) as count 
                FROM transactions 
                GROUP BY status
            """)
            trans_type_agg = cursor.fetchall()
    finally:
        connection.close()

    transaction_types = [t["status"] or "Unknown" for t in trans_type_agg]
    transaction_counts = [t["count"] for t in trans_type_agg]

    return render_template(
        "index.html",
        stats=stats,
        transaction_types=transaction_types,
        transaction_counts=transaction_counts
    )

# ---------------------- Labs CRUD ---------------------- #

@app.route("/labs", methods=["GET", "POST"])
@login_required
def labs():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()

        if not name:
            flash("Lab name is required.", "danger")
        else:
            LabModel.create(name, location, description)
            flash("Lab added successfully.", "success")
            return redirect(url_for("labs"))

    labs_list = LabModel.get_all()
    return render_template("labs.html", labs=labs_list)

@app.route("/labs/<int:lab_id>/edit", methods=["GET", "POST"])
@login_required
def edit_lab(lab_id):
    lab = LabModel.get_by_id(lab_id)
    if not lab:
        flash("Lab not found.", "danger")
        return redirect(url_for("labs"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()

        if not name:
            flash("Lab name is required.", "danger")
        else:
            LabModel.update(lab_id, name, location, description)
            flash("Lab updated successfully.", "success")
            return redirect(url_for("labs"))

    return render_template("edit_lab.html", lab=lab)

@app.route("/labs/<int:lab_id>/delete", methods=["POST"])
@login_required
def delete_lab(lab_id):
    LabModel.delete(lab_id)
    flash("Lab deleted.", "info")
    return redirect(url_for("labs"))

@app.route("/labs/<int:lab_id>/components")
@login_required
def lab_components(lab_id):
    lab = LabModel.get_by_id(lab_id)
    if not lab:
        flash("Lab not found.", "danger")
        return redirect(url_for("labs"))

    components_list = ComponentModel.get_by_lab(lab_id)

    return render_template(
        "components.html",
        components=components_list,
        selected_lab=lab
    )

# ---------------------- Categories CRUD ---------------------- #

@app.route("/categories", methods=["GET", "POST"])
@login_required
def categories():
    labs = LabModel.get_all()

    if request.method == "POST":
        lab_id = request.form.get("lab_id")
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()

        if not (lab_id and name):
            flash("Lab and Category name are required.", "danger")
        else:
            CategoryModel.create(name, description, lab_id)
            flash("Category added successfully.", "success")
            return redirect(url_for("categories"))

    categories_list = CategoryModel.get_all()

    return render_template(
        "categories.html",
        categories=categories_list,
        labs=labs
    )

@app.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])
@login_required
def edit_category(category_id):
    category = CategoryModel.get_by_id(category_id)
    if not category:
        flash("Category not found.", "danger")
        return redirect(url_for("categories"))

    labs = LabModel.get_all()

    if request.method == "POST":
        lab_id = request.form.get("lab_id")
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()

        if not (lab_id and name):
            flash("Lab and Category name are required.", "danger")
        else:
            CategoryModel.update(category_id, name, description, lab_id)
            flash("Category updated successfully.", "success")
            return redirect(url_for("categories"))

    return render_template("edit_category.html", category=category, labs=labs)

@app.route("/categories/<int:category_id>/delete", methods=["POST"])
@login_required
def delete_category(category_id):
    CategoryModel.delete(category_id)
    flash("Category deleted.", "info")
    return redirect(url_for("categories"))

# ---------------------- Components CRUD ---------------------- #

@app.route("/components")
@login_required
def components():
    components_list = ComponentModel.get_all()
    return render_template("components.html", components=components_list, selected_lab=None)

@app.route("/components/add", methods=["GET", "POST"])
@login_required
def add_component():
    labs = LabModel.get_all()
    categories = CategoryModel.get_all()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category_id = request.form.get("category_id")
        lab_id = request.form.get("lab_id")
        quantity = int(request.form.get("quantity") or 0)
        min_stock_level = int(request.form.get("min_stock_level") or 0)
        unit = request.form.get("unit", "").strip()
        description = request.form.get("description", "").strip()
        component_type = request.form.get("component_type", "").strip() or "Other"

        if not (name and category_id and lab_id):
            flash("Name, category, and lab are required.", "danger")
        else:
            ComponentModel.create(
                name, category_id, lab_id,
                quantity, min_stock_level, unit, description,
                component_type
            )
            flash("Component added successfully.", "success")
            return redirect(url_for("components"))

    return render_template(
        "add_component.html",
        labs=labs,
        categories=categories
    )

@app.route("/components/<int:component_id>/edit", methods=["GET", "POST"])
@login_required
def edit_component(component_id):
    component = ComponentModel.get_by_id(component_id)
    if not component:
        flash("Component not found.", "danger")
        return redirect(url_for("components"))

    labs = LabModel.get_all()
    categories = CategoryModel.get_all()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category_id = request.form.get("category_id")
        lab_id = request.form.get("lab_id")
        quantity = int(request.form.get("quantity") or 0)
        min_stock_level = int(request.form.get("min_stock_level") or 0)
        unit = request.form.get("unit", "").strip()
        description = request.form.get("description", "").strip()
        component_type = request.form.get("component_type", "").strip() or "Other"

        if not (name and category_id and lab_id):
            flash("Name, category, and lab are required.", "danger")
        else:
            ComponentModel.update(
                component_id, name, category_id, lab_id,
                quantity, min_stock_level, unit, description,
                component_type
            )
            flash("Component updated successfully.", "success")
            return redirect(url_for("components"))

    return render_template(
        "edit_component.html",
        component=component,
        labs=labs,
        categories=categories
    )

@app.route("/components/<int:component_id>/delete", methods=["POST"])
@login_required
def delete_component(component_id):
    ComponentModel.delete(component_id)
    flash("Component deleted.", "info")
    return redirect(url_for("components"))

# ---------------------- Transactions ---------------------- #

@app.route("/transactions")
@login_required
def transactions():
    transactions_list = TransactionModel.get_all()

    # Summary by status
    connection = db_instance.get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT status, COUNT(*) as count 
                FROM transactions 
                GROUP BY status
            """)
            status_agg = cursor.fetchall()
    finally:
        connection.close()
    
    status_counts = {item["status"] or "Unknown": item["count"] for item in status_agg}

    return render_template(
        "transactions.html",
        transactions=transactions_list,
        status_counts=status_counts
    )

@app.route("/transactions/add", methods=["GET", "POST"])
@login_required
def add_transaction():
    # Get all components
    components = ComponentModel.get_all()
    labs = LabModel.get_all()

    # Add lab_id_str for each component
    for c in components:
        c['lab_id_str'] = str(c.get('lab_id', ''))

    preselected_component_id = request.args.get("component_id")
    preselected_type = request.args.get("transaction_type") or "issue"
    preselected_lab_id = None

    if preselected_component_id:
        comp = next((c for c in components if str(c['id']) == preselected_component_id), None)
        if comp and comp.get('lab_id'):
            preselected_lab_id = str(comp['lab_id'])

    if request.method == "POST":
        transaction_type = request.form.get("transaction_type")
        component_id = request.form.get("component_id")
        lab_id = request.form.get("from_lab_id") or None
        campus = request.form.get("from_campus", "").strip() or None
        person_name = request.form.get("person_name", "").strip()
        purpose = request.form.get("purpose", "").strip()
        notes = request.form.get("notes", "").strip()
        transaction_quantity_raw = request.form.get("transaction_quantity") or "0"

        preselected_component_id = component_id
        preselected_lab_id = lab_id
        preselected_type = transaction_type

        try:
            qty = int(transaction_quantity_raw)
        except ValueError:
            flash("Quantity must be a valid number.", "danger")
            return render_template(
                "add_transaction.html",
                components=components,
                labs=labs,
                preselected_component_id=preselected_component_id,
                preselected_type=preselected_type,
                preselected_lab_id=preselected_lab_id
            )

        if qty <= 0:
            flash("Quantity must be greater than zero.", "danger")
            return render_template(
                "add_transaction.html",
                components=components,
                labs=labs,
                preselected_component_id=preselected_component_id,
                preselected_type=preselected_type,
                preselected_lab_id=preselected_lab_id
            )

        if not lab_id:
            flash("Please select a lab first.", "danger")
            return render_template(
                "add_transaction.html",
                components=components,
                labs=labs,
                preselected_component_id=preselected_component_id,
                preselected_type=preselected_type,
                preselected_lab_id=preselected_lab_id
            )

        if not component_id:
            flash("Please select a component.", "danger")
            return render_template(
                "add_transaction.html",
                components=components,
                labs=labs,
                preselected_component_id=preselected_component_id,
                preselected_type=preselected_type,
                preselected_lab_id=preselected_lab_id
            )

        if not person_name or not purpose:
            flash("Person and Purpose are required.", "danger")
            return render_template(
                "add_transaction.html",
                components=components,
                labs=labs,
                preselected_component_id=preselected_component_id,
                preselected_type=preselected_type,
                preselected_lab_id=preselected_lab_id
            )

        component = ComponentModel.get_by_id(component_id)
        if not component:
            flash("Component not found.", "danger")
            return render_template(
                "add_transaction.html",
                components=components,
                labs=labs,
                preselected_component_id=None,
                preselected_type=preselected_type,
                preselected_lab_id=preselected_lab_id
            )

        try:
            if transaction_type == "issue":
                TransactionModel.create_issue(
                    component, lab_id, campus,
                    person_name, qty, purpose, notes
                )
            elif transaction_type == "return":
                TransactionModel.add_return(
                    component, lab_id, campus,
                    person_name, qty, purpose, notes
                )
            else:
                flash("Invalid transaction type.", "danger")
                return render_template(
                    "add_transaction.html",
                    components=components,
                    labs=labs,
                    preselected_component_id=preselected_component_id,
                    preselected_type=preselected_type,
                    preselected_lab_id=preselected_lab_id
                )
        except ValueError as e:
            flash(str(e), "danger")
            return render_template(
                "add_transaction.html",
                components=components,
                labs=labs,
                preselected_component_id=preselected_component_id,
                preselected_type=preselected_type,
                preselected_lab_id=preselected_lab_id
            )

        flash("Transaction recorded successfully.", "success")
        return redirect(url_for("transactions"))

    return render_template(
        "add_transaction.html",
        components=components,
        labs=labs,
        preselected_component_id=preselected_component_id,
        preselected_type=preselected_type,
        preselected_lab_id=preselected_lab_id
    )

@app.route("/transactions/<int:transaction_id>/edit", methods=["GET", "POST"])
@login_required
def edit_transaction(transaction_id):
    txn = TransactionModel.get_by_id(transaction_id)
    if not txn:
        flash("Transaction not found.", "danger")
        return redirect(url_for("transactions"))

    component = ComponentModel.get_by_id(txn['component_id'])
    lab = LabModel.get_by_id(txn['lab_id']) if txn.get('lab_id') else None

    qty_issued = int(txn.get('qty_issued', 0))
    qty_returned = int(txn.get('qty_returned', 0))
    pending = int(txn.get('pending_qty', qty_issued - qty_returned))

    if request.method == "POST":
        return_now_raw = request.form.get("return_now") or "0"
        notes = request.form.get("notes", "").strip()

        try:
            return_now = int(return_now_raw)
        except ValueError:
            flash("Return quantity must be a valid number.", "danger")
            return redirect(url_for("edit_transaction", transaction_id=transaction_id))

        if return_now <= 0:
            flash("No changes made (return quantity must be > 0).", "info")
            return redirect(url_for("transactions"))

        try:
            TransactionModel.add_return(
                component,
                str(txn.get('lab_id')) if txn.get('lab_id') else None,
                txn.get('campus'),
                txn.get('person_name', ''),
                return_now,
                txn.get('purpose', ''),
                notes
            )
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for("edit_transaction", transaction_id=transaction_id))

        flash("Return transaction recorded successfully.", "success")
        return redirect(url_for("transactions"))

    return render_template(
        "edit_transaction.html",
        txn=txn,
        component=component,
        lab=lab,
        qty_issued=qty_issued,
        qty_returned=qty_returned,
        pending=pending
    )

@app.route("/transactions/<int:transaction_id>/view")
@login_required
def view_transaction(transaction_id):
    txn = TransactionModel.get_by_id(transaction_id)
    if not txn:
        flash("Transaction not found.", "danger")
        return redirect(url_for("transactions"))

    component = ComponentModel.get_by_id(txn['component_id'])
    lab = LabModel.get_by_id(txn['lab_id']) if txn.get('lab_id') else None

    qty_issued = int(txn.get('qty_issued', 0))
    qty_returned = int(txn.get('qty_returned', 0))
    pending = int(txn.get('pending_qty', qty_issued - qty_returned))

    return render_template(
        "view_transaction.html",
        txn=txn,
        component=component,
        lab=lab,
        qty_issued=qty_issued,
        qty_returned=qty_returned,
        pending=pending
    )

# ---------------------- Reports ---------------------- #

@app.route("/reports")
@login_required
def reports():
    connection = db_instance.get_connection()
    try:
        with connection.cursor() as cursor:
            # Components by lab
            cursor.execute("""
                SELECT l.name, COUNT(c.id) as count
                FROM labs l
                LEFT JOIN components c ON l.id = c.lab_id
                GROUP BY l.id, l.name
                ORDER BY l.name
            """)
            components_by_lab = cursor.fetchall()
            
            # Components by category
            cursor.execute("""
                SELECT cat.name, COUNT(c.id) as count
                FROM categories cat
                LEFT JOIN components c ON cat.id = c.category_id
                GROUP BY cat.id, cat.name
                ORDER BY cat.name
            """)
            components_by_category = cursor.fetchall()
            
            # Low stock components
            cursor.execute("""
                SELECT c.*, l.name as lab_name
                FROM components c
                LEFT JOIN labs l ON c.lab_id = l.id
                WHERE c.quantity <= c.min_stock_level
                ORDER BY c.name
            """)
            low_stock_components = cursor.fetchall()
            
            # Transaction counts by status
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM transactions
                GROUP BY status
                ORDER BY status
            """)
            transaction_type_counts = cursor.fetchall()
            
    finally:
        connection.close()

    return render_template(
        "reports.html",
        components_by_lab=components_by_lab,
        components_by_category=components_by_category,
        low_stock_components=low_stock_components,
        transaction_type_counts=transaction_type_counts
    )

# ---------------------- PythonAnywhere Entry Point ---------------------- #

if __name__ == "__main__":
    app.run(debug=True)
