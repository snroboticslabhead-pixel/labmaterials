from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, session
)
from flask_migrate import Migrate
from models import (
    db, User, Lab, Category, Component, Transaction
)
from datetime import datetime
from zoneinfo import ZoneInfo
from functools import wraps

from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)

IST = ZoneInfo("Asia/Kolkata")

# ---------------------- Authentication Logic ---------------------- #
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

        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['user'] = user.username
            flash("Welcome back, Admin!", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid username or password.", "danger")
            
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop('user_id', None)
    session.pop('user', None)
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

# ---------------------- Helper: dashboard stats ---------------------- #
def get_dashboard_stats():
    total_components = Component.query.count()
    total_transactions = Transaction.query.count()
    total_labs = Lab.query.count()
    total_categories = Category.query.count()
    
    pending_returns = Transaction.query.filter(
        Transaction.status.in_(["Issued", "Partially Returned"])
    ).count()

    low_stock_components = Component.query.filter(
        Component.quantity <= Component.min_stock_level
    ).count()

    out_of_stock_components = Component.query.filter(
        db.or_(
            Component.quantity <= 0,
            Component.quantity.is_(None)
        )
    ).count()

    # Lab stats: number of components per lab
    lab_stats = db.session.query(
        Lab.name,
        db.func.count(Component.id).label('component_count')
    ).join(
        Component, Lab.id == Component.lab_id, isouter=True
    ).group_by(Lab.id).order_by(Lab.name).all()

    recent_transactions = Transaction.query.order_by(
        Transaction.issue_date.desc()
    ).limit(5).all()

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

# ---------------------- Routes (Protected) ---------------------- #
@app.route("/")
@login_required
def index():
    stats = get_dashboard_stats()

    # For quick charts on dashboard: transaction counts by STATUS
    trans_type_agg = db.session.query(
        Transaction.status,
        db.func.count(Transaction.id).label('count')
    ).group_by(Transaction.status).all()

    transaction_types = [t[0] or "Unknown" for t in trans_type_agg]
    transaction_counts = [t[1] for t in trans_type_agg]

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
            lab = Lab(name=name, location=location, description=description)
            db.session.add(lab)
            db.session.commit()
            flash("Lab added successfully.", "success")
            return redirect(url_for("labs"))

    labs_list = Lab.query.order_by(Lab.name).all()
    return render_template("labs.html", labs=labs_list)

@app.route("/labs/<int:lab_id>/edit", methods=["GET", "POST"])
@login_required
def edit_lab(lab_id):
    lab = Lab.query.get(lab_id)
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
            lab.name = name
            lab.location = location
            lab.description = description
            db.session.commit()
            flash("Lab updated successfully.", "success")
            return redirect(url_for("labs"))

    return render_template("edit_lab.html", lab=lab)

@app.route("/labs/<int:lab_id>/delete", methods=["POST"])
@login_required
def delete_lab(lab_id):
    lab = Lab.query.get(lab_id)
    if lab:
        db.session.delete(lab)
        db.session.commit()
        flash("Lab deleted.", "info")
    return redirect(url_for("labs"))

@app.route("/labs/<int:lab_id>/components")
@login_required
def lab_components(lab_id):
    lab = Lab.query.get(lab_id)
    if not lab:
        flash("Lab not found.", "danger")
        return redirect(url_for("labs"))

    components_list = Component.query.filter_by(lab_id=lab_id).order_by(Component.name).all()
    components_list = enrich_components_with_status(components_list)

    return render_template(
        "components.html",
        components=components_list,
        selected_lab=lab
    )

# ---------------------- Categories CRUD ---------------------- #
@app.route("/categories", methods=["GET", "POST"])
@login_required
def categories():
    labs = Lab.query.order_by(Lab.name).all()

    if request.method == "POST":
        lab_id = request.form.get("lab_id")
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()

        if not (lab_id and name):
            flash("Lab and Category name are required.", "danger")
        else:
            category = Category(
                name=name, 
                description=description, 
                lab_id=lab_id
            )
            db.session.add(category)
            db.session.commit()
            flash("Category added successfully.", "success")
            return redirect(url_for("categories"))

    categories_list = Category.query.order_by(Category.name).all()
    return render_template(
        "categories.html",
        categories=categories_list,
        labs=labs
    )

@app.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])
@login_required
def edit_category(category_id):
    category = Category.query.get(category_id)
    if not category:
        flash("Category not found.", "danger")
        return redirect(url_for("categories"))

    labs = Lab.query.order_by(Lab.name).all()

    if request.method == "POST":
        lab_id = request.form.get("lab_id")
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()

        if not (lab_id and name):
            flash("Lab and Category name are required.", "danger")
        else:
            category.name = name
            category.description = description
            category.lab_id = lab_id
            db.session.commit()
            flash("Category updated successfully.", "success")
            return redirect(url_for("categories"))

    return render_template("edit_category.html", category=category, labs=labs)

@app.route("/categories/<int:category_id>/delete", methods=["POST"])
@login_required
def delete_category(category_id):
    category = Category.query.get(category_id)
    if category:
        db.session.delete(category)
        db.session.commit()
        flash("Category deleted.", "info")
    return redirect(url_for("categories"))

# ---------------------- Components CRUD ---------------------- #
def enrich_components_with_status(components):
    for c in components:
        qty = c.quantity or 0
        min_stock = c.min_stock_level or 0

        if qty <= 0:
            stock_state = "Out of Stock"
            stock_class = "out"
        elif qty <= min_stock:
            stock_state = "Low Stock"
            stock_class = "low"
        else:
            stock_state = "In Stock"
            stock_class = "instock"

        c.stock_state = stock_state
        c.stock_state_class = stock_class
        c.status_label = stock_state
        c.status_detail = ""

    return components

@app.route("/components")
@login_required
def components():
    components_list = Component.query.order_by(Component.name).all()
    components_list = enrich_components_with_status(components_list)
    return render_template("components.html", components=components_list, selected_lab=None)

@app.route("/components/add", methods=["GET", "POST"])
@login_required
def add_component():
    labs = Lab.query.order_by(Lab.name).all()
    categories = Category.query.order_by(Category.name).all()

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
            component = Component(
                name=name,
                category_id=category_id,
                lab_id=lab_id,
                quantity=quantity,
                min_stock_level=min_stock_level,
                unit=unit,
                description=description,
                component_type=component_type
            )
            db.session.add(component)
            db.session.commit()
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
    component = Component.query.get(component_id)
    if not component:
        flash("Component not found.", "danger")
        return redirect(url_for("components"))

    labs = Lab.query.order_by(Lab.name).all()
    categories = Category.query.order_by(Category.name).all()

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
            component.name = name
            component.category_id = category_id
            component.lab_id = lab_id
            component.quantity = quantity
            component.min_stock_level = min_stock_level
            component.unit = unit
            component.description = description
            component.component_type = component_type
            component.last_updated = datetime.now(IST)
            
            db.session.commit()
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
    component = Component.query.get(component_id)
    if component:
        db.session.delete(component)
        db.session.commit()
        flash("Component deleted.", "info")
    return redirect(url_for("components"))

# ---------------------- Transactions ---------------------- #
@app.route("/transactions")
@login_required
def transactions():
    transactions_list = Transaction.query.order_by(Transaction.issue_date.desc()).all()

    # Summary by status
    status_counts = {}
    for status in ['Issued', 'Partially Returned', 'Completed']:
        count = Transaction.query.filter_by(status=status).count()
        status_counts[status] = count

    return render_template(
        "transactions.html",
        transactions=transactions_list,
        status_counts=status_counts
    )

@app.route("/transactions/add", methods=["GET", "POST"])
@login_required
def add_transaction():
    components = Component.query.order_by(Component.name).all()
    labs = Lab.query.order_by(Lab.name).all()

    preselected_component_id = request.args.get("component_id")
    preselected_type = request.args.get("transaction_type") or "issue"
    preselected_lab_id = None

    if preselected_component_id:
        comp = Component.query.get(preselected_component_id)
        if comp:
            preselected_lab_id = comp.lab_id

    if request.method == "POST":
        transaction_type = request.form.get("transaction_type")
        component_id = request.form.get("component_id")
        lab_id = request.form.get("from_lab_id")
        campus = request.form.get("from_campus", "").strip()
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
                preselected_component_id=None,
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

        component = Component.query.get(component_id)
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
                create_issue_transaction(component, lab_id, campus, person_name, qty, purpose, notes)
            elif transaction_type == "return":
                create_return_transaction(component, lab_id, campus, person_name, qty, purpose, notes)
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

def create_issue_transaction(component, lab_id, campus, person_name, qty, purpose, notes):
    current_stock = component.quantity or 0

    if qty > current_stock:
        raise ValueError(
            f"Cannot issue {qty} units. Only {current_stock} available in stock."
        )

    quantity_after = current_stock - qty
    now = datetime.now(IST)

    # Find existing open transaction
    existing = Transaction.query.filter_by(
        component_id=component.id,
        lab_id=lab_id,
        campus=campus,
        person_name=person_name,
        purpose=purpose,
        status__in=["Issued", "Partially Returned"]
    ).first()

    if existing:
        new_issued = existing.qty_issued + qty
        qty_returned = existing.qty_returned
        pending = new_issued - qty_returned
        status = "Issued" if qty_returned == 0 else (
            "Completed" if pending <= 0 else "Partially Returned"
        )

        existing.qty_issued = new_issued
        existing.pending_qty = pending
        existing.status = status
        existing.quantity_before = current_stock
        existing.quantity_after = quantity_after
        existing.last_action = "issue"
        existing.transaction_quantity = qty
        existing.date = now
        existing.last_updated = now
        existing.notes = notes or existing.notes
    else:
        transaction = Transaction(
            component_id=component.id,
            lab_id=lab_id,
            campus=campus,
            person_name=person_name,
            purpose=purpose,
            qty_issued=qty,
            qty_returned=0,
            pending_qty=qty,
            status="Issued",
            issue_date=now,
            date=now,
            quantity_before=current_stock,
            quantity_after=quantity_after,
            transaction_quantity=qty,
            last_action="issue",
            notes=notes
        )
        db.session.add(transaction)

    # Update component stock
    component.quantity = quantity_after
    component.last_updated = now
    db.session.commit()

def create_return_transaction(component, lab_id, campus, person_name, qty, purpose, notes):
    current_stock = component.quantity or 0
    now = datetime.now(IST)

    # Find existing open transaction
    existing = Transaction.query.filter_by(
        component_id=component.id,
        lab_id=lab_id,
        campus=campus,
        person_name=person_name,
        purpose=purpose,
        status__in=["Issued", "Partially Returned"]
    ).first()

    if not existing:
        raise ValueError(
            "No matching issued transaction found to return against "
            "(check Component / Lab / Campus / Person / Purpose)."
        )

    qty_issued = existing.qty_issued
    qty_returned = existing.qty_returned
    pending = qty_issued - qty_returned

    if pending <= 0:
        raise ValueError("No pending quantity left to return for this transaction.")

    if qty > pending:
        raise ValueError(
            f"Return quantity ({qty}) cannot exceed pending quantity ({pending})."
        )

    new_returned = qty_returned + qty
    new_pending = qty_issued - new_returned
    status = "Completed" if new_pending <= 0 else "Partially Returned"
    quantity_after = current_stock + qty

    existing.qty_returned = new_returned
    existing.pending_qty = new_pending
    existing.status = status
    existing.quantity_before = current_stock
    existing.quantity_after = quantity_after
    existing.last_action = "return"
    existing.transaction_quantity = qty
    existing.date = now
    existing.last_updated = now
    existing.notes = (existing.notes or "") + (
        f"\nReturn: {notes}" if notes else ""
    )

    # Update component stock
    component.quantity = quantity_after
    component.last_updated = now
    db.session.commit()

@app.route("/transactions/<int:transaction_id>/edit", methods=["GET", "POST"])
@login_required
def edit_transaction(transaction_id):
    txn = Transaction.query.get(transaction_id)
    if not txn:
        flash("Transaction not found.", "danger")
        return redirect(url_for("transactions"))

    component = txn.component
    lab = txn.lab

    qty_issued = txn.qty_issued or 0
    qty_returned = txn.qty_returned or 0
    pending = txn.pending_qty or (qty_issued - qty_returned)

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
            create_return_transaction(
                component,
                txn.lab_id,
                txn.campus,
                txn.person_name,
                return_now,
                txn.purpose,
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
    txn = Transaction.query.get(transaction_id)
    if not txn:
        flash("Transaction not found.", "danger")
        return redirect(url_for("transactions"))

    component = txn.component
    lab = txn.lab

    qty_issued = txn.qty_issued or 0
    qty_returned = txn.qty_returned or 0
    pending = txn.pending_qty or (qty_issued - qty_returned)

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
    # Components by lab
    components_by_lab = db.session.query(
        Lab.name,
        db.func.count(Component.id).label('count')
    ).join(
        Component, Lab.id == Component.lab_id, isouter=True
    ).group_by(Lab.id).order_by(Lab.name).all()

    # Components by category
    components_by_category = db.session.query(
        Category.name,
        db.func.count(Component.id).label('count')
    ).join(
        Component, Category.id == Component.category_id, isouter=True
    ).group_by(Category.id).order_by(Category.name).all()

    # Low stock list
    low_stock_components = Component.query.filter(
        Component.quantity <= Component.min_stock_level
    ).order_by(Component.name).all()

    # Transaction counts by status
    transaction_type_counts = db.session.query(
        Transaction.status,
        db.func.count(Transaction.id).label('count')
    ).group_by(Transaction.status).order_by(Transaction.status).all()

    return render_template(
        "reports.html",
        components_by_lab=components_by_lab,
        components_by_category=components_by_category,
        low_stock_components=low_stock_components,
        transaction_type_counts=transaction_type_counts
    )

# ---------------------- Create Admin User ---------------------- #
@app.before_first_request
def create_admin():
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@example.com',
            role='admin'
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()

if __name__ == "__main__":
    app.run(debug=True)
