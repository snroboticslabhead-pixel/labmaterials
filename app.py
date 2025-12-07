from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, session
)
from functools import wraps
from sqlalchemy import func, or_, and_
from sqlalchemy.orm import joinedload

from config import Config
from models import db, User, Lab, Category, Component, Transaction
import pytz

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

IST = pytz.timezone('Asia/Kolkata')

# ---------------------- Authentication Logic ---------------------- #
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

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

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['user'] = username
            flash("Welcome back, Admin!", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid username or password.", "danger")
            
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop('user', None)
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

# ---------------------- Helper Functions ---------------------- #
def get_dashboard_stats():
    total_components = Component.query.count()
    total_transactions = Transaction.query.count()
    total_labs = Lab.query.count()
    total_categories = Category.query.count()
    
    # Count pending returns
    pending_returns = Transaction.query.filter(
        Transaction.status.in_(['Issued', 'Partially Returned'])
    ).count()
    
    # Count low stock components
    low_stock_components = Component.query.filter(
        Component.quantity <= Component.min_stock_level
    ).count()
    
    # Count out of stock components
    out_of_stock_components = Component.query.filter(
        or_(
            Component.quantity <= 0,
            Component.quantity == None
        )
    ).count()
    
    # Lab stats
    lab_stats = db.session.query(
        Lab.name.label('lab_name'),
        func.count(Component.id).label('component_count')
    ).outerjoin(Component, Lab.id == Component.lab_id)\
     .group_by(Lab.id, Lab.name)\
     .order_by(Lab.name)\
     .all()
    
    lab_stats_list = []
    for stat in lab_stats:
        lab_stats_list.append({
            'lab_name': stat.lab_name or "Unassigned",
            'component_count': stat.component_count or 0
        })
    
    # Recent transactions
    recent_transactions = Transaction.query\
        .options(joinedload(Transaction.component))\
        .order_by(Transaction.date.desc())\
        .limit(5)\
        .all()
    
    return {
        "total_components": total_components,
        "total_transactions": total_transactions,
        "total_labs": total_labs,
        "total_categories": total_categories,
        "pending_returns": pending_returns,
        "low_stock_components": low_stock_components,
        "out_of_stock_components": out_of_stock_components,
        "lab_stats": lab_stats_list,
        "recent_transactions": recent_transactions
    }

# ---------------------- Routes ---------------------- #
@app.route("/")
@login_required
def index():
    stats = get_dashboard_stats()
    
    # Transaction counts by status
    trans_type_agg = db.session.query(
        Transaction.status,
        func.count(Transaction.id).label('count')
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
            # Check for duplicate lab name
            existing_lab = Lab.query.filter_by(name=name).first()
            if existing_lab:
                flash("A lab with this name already exists.", "danger")
            else:
                new_lab = Lab(name=name, location=location, description=description)
                db.session.add(new_lab)
                db.session.commit()
                flash("Lab added successfully.", "success")
            return redirect(url_for("labs"))

    labs_list = Lab.query.order_by(Lab.name).all()
    return render_template("labs.html", labs=labs_list)

@app.route("/labs/<int:lab_id>/edit", methods=["GET", "POST"])
@login_required
def edit_lab(lab_id):
    lab = Lab.query.get_or_404(lab_id)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()

        if not name:
            flash("Lab name is required.", "danger")
        else:
            # Check for duplicate lab name (excluding current lab)
            existing_lab = Lab.query.filter(Lab.name == name, Lab.id != lab_id).first()
            if existing_lab:
                flash("A lab with this name already exists.", "danger")
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
    lab = Lab.query.get_or_404(lab_id)
    
    # Check if lab has any components
    if lab.components:
        flash("Cannot delete lab that has components. Please delete or reassign components first.", "danger")
    else:
        db.session.delete(lab)
        db.session.commit()
        flash("Lab deleted.", "info")
    
    return redirect(url_for("labs"))

@app.route("/labs/<int:lab_id>/components")
@login_required
def lab_components(lab_id):
    lab = Lab.query.get_or_404(lab_id)
    
    components_list = Component.query\
        .filter_by(lab_id=lab_id)\
        .options(joinedload(Component.category), joinedload(Component.lab))\
        .order_by(Component.name)\
        .all()
    
    # Enrich with status
    for component in components_list:
        qty = component.quantity or 0
        min_stock = component.min_stock_level or 0
        
        if qty <= 0:
            component.stock_state = "Out of Stock"
            component.stock_state_class = "out"
        elif qty <= min_stock:
            component.stock_state = "Low Stock"
            component.stock_state_class = "low"
        else:
            component.stock_state = "In Stock"
            component.stock_state_class = "instock"
        
        component.status_label = component.stock_state

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
            # Check for duplicate category name in the same lab
            existing_category = Category.query.filter_by(
                name=name, lab_id=lab_id
            ).first()
            
            if existing_category:
                flash("A category with this name already exists in this lab.", "danger")
            else:
                new_category = Category(
                    name=name,
                    description=description,
                    lab_id=lab_id
                )
                db.session.add(new_category)
                db.session.commit()
                flash("Category added successfully.", "success")
            return redirect(url_for("categories"))

    # Get categories with component counts and total quantities
    categories_list = []
    all_categories = Category.query\
        .options(joinedload(Category.lab))\
        .order_by(Category.name)\
        .all()
    
    for cat in all_categories:
        # Get components in this category
        components_in_cat = Component.query.filter_by(category_id=cat.id).all()
        component_count = len(components_in_cat)
        total_quantity = sum(c.quantity or 0 for c in components_in_cat)
        
        cat_dict = {
            'id': cat.id,
            'name': cat.name,
            'description': cat.description,
            'lab_id': cat.lab_id,
            'created_at': cat.created_at,
            'lab': cat.lab,
            'component_count': component_count,
            'total_quantity': total_quantity
        }
        categories_list.append(cat_dict)

    return render_template(
        "categories.html",
        categories=categories_list,
        labs=labs
    )

@app.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])
@login_required
def edit_category(category_id):
    category = Category.query.get_or_404(category_id)
    labs = Lab.query.order_by(Lab.name).all()

    if request.method == "POST":
        lab_id = request.form.get("lab_id")
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()

        if not (lab_id and name):
            flash("Lab and Category name are required.", "danger")
        else:
            # Check for duplicate category name in the same lab (excluding current)
            existing_category = Category.query.filter(
                Category.name == name,
                Category.lab_id == lab_id,
                Category.id != category_id
            ).first()
            
            if existing_category:
                flash("A category with this name already exists in this lab.", "danger")
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
    category = Category.query.get_or_404(category_id)
    
    # Check if category has any components
    if category.components:
        flash("Cannot delete category that has components. Please delete or reassign components first.", "danger")
    else:
        db.session.delete(category)
        db.session.commit()
        flash("Category deleted.", "info")
    
    return redirect(url_for("categories"))

# ---------------------- Components CRUD ---------------------- #
@app.route("/components")
@login_required
def components():
    components_list = Component.query\
        .options(joinedload(Component.category), joinedload(Component.lab))\
        .order_by(Component.name)\
        .all()
    
    # Enrich with status
    for component in components_list:
        qty = component.quantity or 0
        min_stock = component.min_stock_level or 0
        
        if qty <= 0:
            component.stock_state = "Out of Stock"
            component.stock_state_class = "out"
        elif qty <= min_stock:
            component.stock_state = "Low Stock"
            component.stock_state_class = "low"
        else:
            component.stock_state = "In Stock"
            component.stock_state_class = "instock"
        
        component.status_label = component.stock_state

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
            new_component = Component(
                name=name,
                category_id=category_id,
                lab_id=lab_id,
                quantity=quantity,
                min_stock_level=min_stock_level,
                unit=unit,
                description=description,
                component_type=component_type
            )
            db.session.add(new_component)
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
    component = Component.query.get_or_404(component_id)
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
    component = Component.query.get_or_404(component_id)
    
    # Check if component has any transactions
    if component.transactions:
        flash("Cannot delete component that has transaction history. Please delete transactions first.", "danger")
    else:
        db.session.delete(component)
        db.session.commit()
        flash("Component deleted.", "info")
    
    return redirect(url_for("components"))

# ---------------------- Transactions ---------------------- #
@app.route("/transactions")
@login_required
def transactions():
    transactions_list = Transaction.query\
        .options(joinedload(Transaction.component), joinedload(Transaction.lab))\
        .order_by(Transaction.issue_date.desc())\
        .all()
    
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
    components = Component.query\
        .options(joinedload(Component.lab))\
        .order_by(Component.name)\
        .all()
    
    labs = Lab.query.order_by(Lab.name).all()

    # Helper for Jinja/JS
    for c in components:
        c.lab_id_str = str(c.lab_id)

    preselected_component_id = request.args.get("component_id")
    preselected_type = request.args.get("transaction_type") or "issue"
    preselected_lab_id = None

    # If opened from Components "Issue/Return" quick action
    if preselected_component_id:
        comp = Component.query.get(preselected_component_id)
        if comp and comp.lab_id:
            preselected_lab_id = str(comp.lab_id)

    if request.method == "POST":
        transaction_type = request.form.get("transaction_type")
        component_id = request.form.get("component_id")
        lab_id = request.form.get("from_lab_id")
        campus = request.form.get("from_campus", "").strip() or None
        person_name = request.form.get("person_name", "").strip()
        purpose = request.form.get("purpose", "").strip()
        notes = request.form.get("notes", "").strip()
        transaction_quantity_raw = request.form.get("transaction_quantity") or "0"

        # Keep selections on error
        preselected_component_id = component_id
        preselected_lab_id = lab_id
        preselected_type = transaction_type

        # Validate quantity
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

        # Basic validation
        if not (lab_id and component_id and person_name and purpose):
            flash("Lab, component, person, and purpose are required.", "danger")
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

        # Business logic
        try:
            current_stock = component.quantity or 0
            
            if transaction_type == "issue":
                if qty > current_stock:
                    flash(f"Cannot issue {qty} units. Only {current_stock} available in stock.", "danger")
                    return render_template(
                        "add_transaction.html",
                        components=components,
                        labs=labs,
                        preselected_component_id=preselected_component_id,
                        preselected_type=preselected_type,
                        preselected_lab_id=preselected_lab_id
                    )
                
                # Find existing open transaction
                existing = Transaction.query.filter_by(
                    component_id=component_id,
                    lab_id=lab_id,
                    campus=campus,
                    person_name=person_name,
                    purpose=purpose,
                    status=Transaction.status.in_(['Issued', 'Partially Returned'])
                ).first()
                
                quantity_after = current_stock - qty
                
                if existing:
                    new_issued = existing.qty_issued + qty
                    pending = new_issued - existing.qty_returned
                    status = "Issued" if existing.qty_returned == 0 else (
                        "Completed" if pending <= 0 else "Partially Returned"
                    )
                    
                    existing.qty_issued = new_issued
                    existing.pending_qty = pending
                    existing.status = status
                    existing.quantity_before = current_stock
                    existing.quantity_after = quantity_after
                    existing.last_action = "issue"
                    existing.transaction_quantity = qty
                    existing.date = datetime.now(IST)
                    existing.notes = notes or existing.notes
                else:
                    new_transaction = Transaction(
                        component_id=component_id,
                        lab_id=lab_id,
                        campus=campus,
                        person_name=person_name,
                        purpose=purpose,
                        qty_issued=qty,
                        qty_returned=0,
                        pending_qty=qty,
                        status="Issued",
                        quantity_before=current_stock,
                        quantity_after=quantity_after,
                        transaction_quantity=qty,
                        last_action="issue",
                        notes=notes
                    )
                    db.session.add(new_transaction)
                
                # Update component stock
                component.quantity = quantity_after
                
            elif transaction_type == "return":
                # Find existing transaction to return against
                existing = Transaction.query.filter_by(
                    component_id=component_id,
                    lab_id=lab_id,
                    campus=campus,
                    person_name=person_name,
                    purpose=purpose,
                    status=Transaction.status.in_(['Issued', 'Partially Returned'])
                ).first()
                
                if not existing:
                    flash("No matching issued transaction found to return against.", "danger")
                    return render_template(
                        "add_transaction.html",
                        components=components,
                        labs=labs,
                        preselected_component_id=preselected_component_id,
                        preselected_type=preselected_type,
                        preselected_lab_id=preselected_lab_id
                    )
                
                qty_issued = existing.qty_issued
                qty_returned = existing.qty_returned
                pending = qty_issued - qty_returned
                
                if pending <= 0:
                    flash("No pending quantity left to return for this transaction.", "danger")
                    return redirect(url_for('add_transaction'))
                
                if qty > pending:
                    flash(f"Return quantity ({qty}) cannot exceed pending quantity ({pending}).", "danger")
                    return redirect(url_for('add_transaction'))
                
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
                existing.date = datetime.now(IST)
                existing.notes = (existing.notes or "") + (f"\nReturn: {notes}" if notes else "")
                
                # Update component stock
                component.quantity = quantity_after
            
            db.session.commit()
            flash("Transaction recorded successfully.", "success")
            return redirect(url_for("transactions"))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")
            return render_template(
                "add_transaction.html",
                components=components,
                labs=labs,
                preselected_component_id=preselected_component_id,
                preselected_type=preselected_type,
                preselected_lab_id=preselected_lab_id
            )

    # GET request
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
    txn = Transaction.query.get_or_404(transaction_id)
    component = Component.query.get(txn.component_id)
    lab = Lab.query.get(txn.lab_id)

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
        
        if pending <= 0:
            flash("No pending quantity left to return.", "danger")
            return redirect(url_for("edit_transaction", transaction_id=transaction_id))
        
        if return_now > pending:
            flash(f"Return quantity ({return_now}) cannot exceed pending quantity ({pending}).", "danger")
            return redirect(url_for("edit_transaction", transaction_id=transaction_id))
        
        try:
            current_stock = component.quantity or 0
            new_returned = qty_returned + return_now
            new_pending = qty_issued - new_returned
            status = "Completed" if new_pending <= 0 else "Partially Returned"
            quantity_after = current_stock + return_now
            
            txn.qty_returned = new_returned
            txn.pending_qty = new_pending
            txn.status = status
            txn.quantity_before = current_stock
            txn.quantity_after = quantity_after
            txn.last_action = "return"
            txn.transaction_quantity = return_now
            txn.date = datetime.now(IST)
            txn.notes = (txn.notes or "") + (f"\nReturn: {notes}" if notes else "")
            
            # Update component stock
            component.quantity = quantity_after
            
            db.session.commit()
            flash("Return transaction recorded successfully.", "success")
            return redirect(url_for("transactions"))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")
            return redirect(url_for("edit_transaction", transaction_id=transaction_id))

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
    txn = Transaction.query.get_or_404(transaction_id)
    component = Component.query.get(txn.component_id)
    lab = Lab.query.get(txn.lab_id)

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
        func.count(Component.id).label('count')
    ).outerjoin(Component, Lab.id == Component.lab_id)\
     .group_by(Lab.id, Lab.name)\
     .order_by(Lab.name)\
     .all()
    
    components_by_lab_list = [{'name': row[0] or 'Unassigned', 'count': row[1]} for row in components_by_lab]

    # Components by category
    components_by_category = db.session.query(
        Category.name,
        func.count(Component.id).label('count')
    ).outerjoin(Component, Category.id == Component.category_id)\
     .group_by(Category.id, Category.name)\
     .order_by(Category.name)\
     .all()
    
    components_by_category_list = [{'name': row[0] or 'Unassigned', 'count': row[1]} for row in components_by_category]

    # Low stock list
    low_stock_components = Component.query\
        .options(joinedload(Component.lab))\
        .filter(Component.quantity <= Component.min_stock_level)\
        .order_by(Component.name)\
        .all()
    
    low_stock_list = []
    for comp in low_stock_components:
        low_stock_list.append({
            'id': comp.id,
            'name': comp.name,
            'quantity': comp.quantity,
            'min_stock_level': comp.min_stock_level,
            'unit': comp.unit,
            'lab_name': comp.lab.name if comp.lab else None
        })

    # Transaction counts by status
    transaction_type_counts = db.session.query(
        Transaction.status,
        func.count(Transaction.id).label('count')
    ).group_by(Transaction.status)\
     .order_by(Transaction.status)\
     .all()
    
    transaction_type_counts_list = [{'status': row[0] or 'Unknown', 'count': row[1]} for row in transaction_type_counts]

    return render_template(
        "reports.html",
        components_by_lab=components_by_lab_list,
        components_by_category=components_by_category_list,
        low_stock_components=low_stock_list,
        transaction_type_counts=transaction_type_counts_list
    )

# ---------------------- Database Initialization ---------------------- #
def create_tables():
    with app.app_context():
        db.create_all()
        
        # Create initial admin user
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@lab.com',
                password='admin123',  # In production, hash this!
                role='admin',
                lab_name='Main Lab'
            )
            db.session.add(admin)
            db.session.commit()
            print("Initial admin user created")

if __name__ == "__main__":
    create_tables()
    app.run(debug=True)
