from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, session, g
)
from functools import wraps
import pymysql

from config import Config
from models import LabModel, CategoryModel, ComponentModel, TransactionModel


app = Flask(__name__)
app.config.from_object(Config)


# ---------------------- MySQL Connection Helper ---------------------- #

def get_db():
    """
    Returns a per-request MySQL connection stored in Flask's `g`.
    Uses DictCursor so rows behave like dictionaries.
    """
    if "db" not in g:
        g.db = pymysql.connect(
            host=app.config["MYSQL_HOST"],
            user=app.config["MYSQL_USER"],
            password=app.config["MYSQL_PASSWORD"],
            database=app.config["MYSQL_DB"],
            port=app.config["MYSQL_PORT"],
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
        )
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ---------------------- Authentication Logic ---------------------- #

# Hardcoded Credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


@app.route("/login", methods=["GET", "POST"])
def login():
    # If already logged in, redirect to dashboard
    if "user" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["user"] = username
            flash("Welcome back, Admin!", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid username or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ---------------------- Helper: dashboard stats ---------------------- #

def get_dashboard_stats(db):
    with db.cursor() as cur:
        # Total components
        cur.execute("SELECT COUNT(*) AS cnt FROM components")
        total_components = cur.fetchone()["cnt"]

        # Total transactions
        cur.execute("SELECT COUNT(*) AS cnt FROM transactions")
        total_transactions = cur.fetchone()["cnt"]

        # Labs
        cur.execute("SELECT COUNT(*) AS cnt FROM labs")
        total_labs = cur.fetchone()["cnt"]

        # Categories
        cur.execute("SELECT COUNT(*) AS cnt FROM categories")
        total_categories = cur.fetchone()["cnt"]

        # Pending returns = Issued or Partially Returned
        cur.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM transactions
            WHERE status IN ('Issued', 'Partially Returned')
            """
        )
        pending_returns = cur.fetchone()["cnt"]

        # Low stock components
        cur.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM components
            WHERE quantity <= min_stock_level
            """
        )
        low_stock_components = cur.fetchone()["cnt"]

        # Out of stock components
        cur.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM components
            WHERE quantity <= 0 OR quantity IS NULL
            """
        )
        out_of_stock_components = cur.fetchone()["cnt"]

        # Lab stats: components per lab
        cur.execute(
            """
            SELECT
                l.id AS lab_id,
                l.name AS lab_name,
                COUNT(c.id) AS component_count
            FROM labs l
            LEFT JOIN components c ON c.lab_id = l.id
            GROUP BY l.id, l.name
            ORDER BY l.name ASC
            """
        )
        lab_rows = cur.fetchall()

    lab_stats = [
        {
            "_id": row["lab_id"],
            "lab_name": row["lab_name"],
            "component_count": row["component_count"],
        }
        for row in lab_rows
    ]

    recent_transactions = TransactionModel.get_recent(db, limit=5)

    return {
        "total_components": total_components,
        "total_transactions": total_transactions,
        "total_labs": total_labs,
        "total_categories": total_categories,
        "pending_returns": pending_returns,
        "low_stock_components": low_stock_components,
        "out_of_stock_components": out_of_stock_components,
        "lab_stats": lab_stats,
        "recent_transactions": recent_transactions,
    }


# ---------------------- Routes (Protected) ---------------------- #

@app.route("/")
@login_required
def index():
    db = get_db()
    stats = get_dashboard_stats(db)

    with db.cursor() as cur:
        cur.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM transactions
            GROUP BY status
            """
        )
        trans_type_agg = cur.fetchall()

    transaction_types = [row["status"] or "Unknown" for row in trans_type_agg]
    transaction_counts = [row["count"] for row in trans_type_agg]

    return render_template(
        "index.html",
        stats=stats,
        transaction_types=transaction_types,
        transaction_counts=transaction_counts,
    )


# ---------------------- Labs CRUD ---------------------- #

@app.route("/labs", methods=["GET", "POST"])
@login_required
def labs():
    db = get_db()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()

        if not name:
            flash("Lab name is required.", "danger")
        else:
            LabModel.create(db, name, location, description)
            flash("Lab added successfully.", "success")
            return redirect(url_for("labs"))

    labs_list = LabModel.get_all(db)
    return render_template("labs.html", labs=labs_list)


@app.route("/labs/<lab_id>/edit", methods=["GET", "POST"])
@login_required
def edit_lab(lab_id):
    db = get_db()
    lab = LabModel.get_by_id(db, lab_id)
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
            LabModel.update(db, lab_id, name, location, description)
            flash("Lab updated successfully.", "success")
            return redirect(url_for("labs"))

    return render_template("edit_lab.html", lab=lab)


@app.route("/labs/<lab_id>/delete", methods=["POST"])
@login_required
def delete_lab(lab_id):
    db = get_db()
    LabModel.delete(db, lab_id)
    flash("Lab deleted.", "info")
    return redirect(url_for("labs"))


# 🔹 NEW: View components for a specific lab only
@app.route("/labs/<lab_id>/components")
@login_required
def lab_components(lab_id):
    db = get_db()
    lab = LabModel.get_by_id(db, lab_id)
    if not lab:
        flash("Lab not found.", "danger")
        return redirect(url_for("labs"))

    components_list = ComponentModel.get_by_lab(db, lab_id)
    components_list = ComponentModel.enrich_with_status(db, components_list)

    return render_template(
        "components.html",
        components=components_list,
        selected_lab=lab,
    )


# ---------------------- Categories CRUD (Lab-wise) ---------------------- #

@app.route("/categories", methods=["GET", "POST"])
@login_required
def categories():
    db = get_db()
    labs = LabModel.get_all(db)

    if request.method == "POST":
        lab_id = request.form.get("lab_id")
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()

        if not (lab_id and name):
            flash("Lab and Category name are required.", "danger")
        else:
            CategoryModel.create(db, name, description, lab_id)
            flash("Category added successfully.", "success")
            return redirect(url_for("categories"))

    categories_list = CategoryModel.get_all(db)

    return render_template(
        "categories.html",
        categories=categories_list,
        labs=labs,
    )


@app.route("/categories/<category_id>/edit", methods=["GET", "POST"])
@login_required
def edit_category(category_id):
    db = get_db()
    category = CategoryModel.get_by_id(db, category_id)
    if not category:
        flash("Category not found.", "danger")
        return redirect(url_for("categories"))

    labs = LabModel.get_all(db)

    if request.method == "POST":
        lab_id = request.form.get("lab_id")
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()

        if not (lab_id and name):
            flash("Lab and Category name are required.", "danger")
        else:
            CategoryModel.update(db, category_id, name, description, lab_id)
            flash("Category updated successfully.", "success")
            return redirect(url_for("categories"))

    return render_template("edit_category.html", category=category, labs=labs)


@app.route("/categories/<category_id>/delete", methods=["POST"])
@login_required
def delete_category(category_id):
    db = get_db()
    CategoryModel.delete(db, category_id)
    flash("Category deleted.", "info")
    return redirect(url_for("categories"))


# ---------------------- Components CRUD ---------------------- #

@app.route("/components")
@login_required
def components():
    db = get_db()
    components_list = ComponentModel.get_all(db)
    components_list = ComponentModel.enrich_with_status(db, components_list)
    # selected_lab is None here; template will show "All Components"
    return render_template(
        "components.html",
        components=components_list,
        selected_lab=None,
    )


@app.route("/components/add", methods=["GET", "POST"])
@login_required
def add_component():
    db = get_db()
    labs = LabModel.get_all(db)
    categories = CategoryModel.get_all(db)

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
                db,
                name,
                category_id,
                lab_id,
                quantity,
                min_stock_level,
                unit,
                description,
                component_type=component_type,
            )
            flash("Component added successfully.", "success")
            return redirect(url_for("components"))

    return render_template(
        "add_component.html",
        labs=labs,
        categories=categories,
    )


@app.route("/components/<component_id>/edit", methods=["GET", "POST"])
@login_required
def edit_component(component_id):
    db = get_db()
    component = ComponentModel.get_by_id(db, component_id)
    if not component:
        flash("Component not found.", "danger")
        return redirect(url_for("components"))

    labs = LabModel.get_all(db)
    categories = CategoryModel.get_all(db)

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
                db,
                component_id,
                name,
                category_id,
                lab_id,
                quantity,
                min_stock_level,
                unit,
                description,
                component_type=component_type,
            )
            flash("Component updated successfully.", "success")
            return redirect(url_for("components"))

    return render_template(
        "edit_component.html",
        component=component,
        labs=labs,
        categories=categories,
    )


@app.route("/components/<component_id>/delete", methods=["POST"])
@login_required
def delete_component(component_id):
    db = get_db()
    ComponentModel.delete(db, component_id)
    flash("Component deleted.", "info")
    return redirect(url_for("components"))


# ---------------------- Transactions (Issue / Return on same line) ---------------------- #

@app.route("/transactions")
@login_required
def transactions():
    db = get_db()
    transactions_list = TransactionModel.get_all(db)

    # Summary by status (Issued / Partially Returned / Completed)
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM transactions
            GROUP BY status
            """
        )
        status_agg = cur.fetchall()

    status_counts = {item["status"] or "Unknown": item["count"] for item in status_agg}

    return render_template(
        "transactions.html",
        transactions=transactions_list,
        status_counts=status_counts,
    )


@app.route("/transactions/add", methods=["GET", "POST"])
@login_required
def add_transaction():
    db = get_db()
    components = ComponentModel.get_all(db)
    labs = LabModel.get_all(db)

    # Add a helper string lab_id for each component (for Jinja/JS)
    for c in components:
        c["lab_id_str"] = str(c.get("lab_id") or "")

    preselected_component_id = request.args.get("component_id")
    preselected_type = request.args.get("transaction_type") or "issue"
    preselected_lab_id = None

    # If opened from Components "Issue/Return" quick action, auto-detect lab
    if preselected_component_id:
        comp = ComponentModel.get_by_id(db, preselected_component_id)
        if comp and comp.get("lab_id"):
            preselected_lab_id = str(comp["lab_id"])

    if request.method == "POST":
        transaction_type = request.form.get("transaction_type")
        component_id = request.form.get("component_id")
        lab_id = request.form.get("from_lab_id") or None
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
                preselected_lab_id=preselected_lab_id,
            )

        if qty <= 0:
            flash("Quantity must be greater than zero.", "danger")
            return render_template(
                "add_transaction.html",
                components=components,
                labs=labs,
                preselected_component_id=preselected_component_id,
                preselected_type=preselected_type,
                preselected_lab_id=preselected_lab_id,
            )

        # Basic required fields
        if not lab_id:
            flash("Please select a lab first.", "danger")
            return render_template(
                "add_transaction.html",
                components=components,
                labs=labs,
                preselected_component_id=preselected_component_id,
                preselected_type=preselected_type,
                preselected_lab_id=preselected_lab_id,
            )

        if not component_id:
            flash("Please select a component.", "danger")
            return render_template(
                "add_transaction.html",
                components=components,
                labs=labs,
                preselected_component_id=preselected_component_id,
                preselected_type=preselected_type,
                preselected_lab_id=preselected_lab_id,
            )

        if not person_name or not purpose:
            flash("Person and Purpose are required.", "danger")
            return render_template(
                "add_transaction.html",
                components=components,
                labs=labs,
                preselected_component_id=preselected_component_id,
                preselected_type=preselected_type,
                preselected_lab_id=preselected_lab_id,
            )

        component = ComponentModel.get_by_id(db, component_id)
        if not component:
            flash("Component not found.", "danger")
            return render_template(
                "add_transaction.html",
                components=components,
                labs=labs,
                preselected_component_id=None,
                preselected_type=preselected_type,
                preselected_lab_id=preselected_lab_id,
            )

        # Business logic using new model
        try:
            if transaction_type == "issue":
                TransactionModel.create_issue(
                    db,
                    component,
                    lab_id,
                    campus,
                    person_name,
                    qty,
                    purpose,
                    notes,
                )
            elif transaction_type == "return":
                TransactionModel.add_return(
                    db,
                    component,
                    lab_id,
                    campus,
                    person_name,
                    qty,
                    purpose,
                    notes,
                )
            else:
                flash("Invalid transaction type.", "danger")
                return render_template(
                    "add_transaction.html",
                    components=components,
                    labs=labs,
                    preselected_component_id=preselected_component_id,
                    preselected_type=preselected_type,
                    preselected_lab_id=preselected_lab_id,
                )
        except ValueError as e:
            flash(str(e), "danger")
            return render_template(
                "add_transaction.html",
                components=components,
                labs=labs,
                preselected_component_id=preselected_component_id,
                preselected_type=preselected_type,
                preselected_lab_id=preselected_lab_id,
            )

        flash("Transaction recorded successfully.", "success")
        return redirect(url_for("transactions"))

    # GET request
    return render_template(
        "add_transaction.html",
        components=components,
        labs=labs,
        preselected_component_id=preselected_component_id,
        preselected_type=preselected_type,
        preselected_lab_id=preselected_lab_id,
    )


@app.route("/transactions/<transaction_id>/edit", methods=["GET", "POST"])
@login_required
def edit_transaction(transaction_id):
    db = get_db()
    txn = TransactionModel.get_by_id(db, transaction_id)
    if not txn:
        flash("Transaction not found.", "danger")
        return redirect(url_for("transactions"))

    component = ComponentModel.get_by_id(db, txn["component_id"])
    lab = LabModel.get_by_id(db, txn["lab_id"]) if txn.get("lab_id") else None

    qty_issued = int(txn.get("qty_issued", 0))
    qty_returned = int(txn.get("qty_returned", 0))
    pending = int(txn.get("pending_qty", qty_issued - qty_returned))

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
                db,
                component,
                str(txn.get("lab_id")) if txn.get("lab_id") else None,
                txn.get("campus"),
                txn.get("person_name", ""),
                return_now,
                txn.get("purpose", ""),
                notes,
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
        pending=pending,
    )


@app.route("/transactions/<transaction_id>/view")
@login_required
def view_transaction(transaction_id):
    db = get_db()
    txn = TransactionModel.get_by_id(db, transaction_id)
    if not txn:
        flash("Transaction not found.", "danger")
        return redirect(url_for("transactions"))

    component = ComponentModel.get_by_id(db, txn["component_id"])
    lab = LabModel.get_by_id(db, txn["lab_id"]) if txn.get("lab_id") else None

    qty_issued = int(txn.get("qty_issued", 0))
    qty_returned = int(txn.get("qty_returned", 0))
    pending = int(txn.get("pending_qty", qty_issued - qty_returned))

    return render_template(
        "view_transaction.html",
        txn=txn,
        component=component,
        lab=lab,
        qty_issued=qty_issued,
        qty_returned=qty_returned,
        pending=pending,
    )


# ---------------------- Reports ---------------------- #

@app.route("/reports")
@login_required
def reports():
    db = get_db()

    # Components by lab
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT
                COALESCE(l.name, 'Unassigned') AS lab_name,
                COUNT(c.id) AS cnt
            FROM labs l
            LEFT JOIN components c ON c.lab_id = l.id
            GROUP BY l.name
            ORDER BY lab_name ASC
            """
        )
        rows = cur.fetchall()
    components_by_lab = [{"_id": r["lab_name"], "count": r["cnt"]} for r in rows]

    # Components by category
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT
                COALESCE(cat.name, 'Unassigned') AS category_name,
                COUNT(c.id) AS cnt
            FROM categories cat
            LEFT JOIN components c ON c.category_id = cat.id
            GROUP BY cat.name
            ORDER BY category_name ASC
            """
        )
        rows2 = cur.fetchall()
    components_by_category = [{"_id": r["category_name"], "count": r["cnt"]} for r in rows2]

    # Low stock list
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT *
            FROM components
            WHERE quantity <= min_stock_level
            ORDER BY name ASC
            """
        )
        low_stock_components = cur.fetchall()

    # Transaction counts by status
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM transactions
            GROUP BY status
            ORDER BY status ASC
            """
        )
        ttc = cur.fetchall()
    transaction_type_counts = [{"_id": row["status"], "count": row["count"]} for row in ttc]

    return render_template(
        "reports.html",
        components_by_lab=components_by_lab,
        components_by_category=components_by_category,
        low_stock_components=low_stock_components,
        transaction_type_counts=transaction_type_counts,
    )


if __name__ == "__main__":
    # For local testing. On PythonAnywhere, use WSGI file pointing to `app`.
    app.run(debug=True)
