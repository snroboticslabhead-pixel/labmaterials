from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, session
)
from functools import wraps
import pymysql
from pymysql.cursors import DictCursor

from config import Config
from models import LabModel, CategoryModel, ComponentModel, TransactionModel

app = Flask(__name__)
app.config.from_object(Config)


# ---------- Simple MySQL connection helper ---------- #
def get_db_connection():
    return pymysql.connect(
        host=app.config["MYSQL_HOST"],
        user=app.config["MYSQL_USER"],
        password=app.config["MYSQL_PASSWORD"],
        database=app.config["MYSQL_DB"],
        cursorclass=DictCursor,
        autocommit=True,
    )


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
def get_dashboard_stats():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Total counts
            cur.execute("SELECT COUNT(*) AS cnt FROM components")
            total_components = cur.fetchone()["cnt"]

            cur.execute("SELECT COUNT(*) AS cnt FROM transactions")
            total_transactions = cur.fetchone()["cnt"]

            cur.execute("SELECT COUNT(*) AS cnt FROM labs")
            total_labs = cur.fetchone()["cnt"]

            cur.execute("SELECT COUNT(*) AS cnt FROM categories")
            total_categories = cur.fetchone()["cnt"]

            # Pending returns
            cur.execute("""
                SELECT COUNT(*) AS cnt
                FROM transactions
                WHERE status IN ('Issued', 'Partially Returned')
            """)
            pending_returns = cur.fetchone()["cnt"]

            # Low stock
            cur.execute("""
                SELECT COUNT(*) AS cnt
                FROM components
                WHERE quantity <= min_stock_level
            """)
            low_stock_components = cur.fetchone()["cnt"]

            # Out of stock
            cur.execute("""
                SELECT COUNT(*) AS cnt
                FROM components
                WHERE quantity <= 0 OR quantity IS NULL
            """)
            out_of_stock_components = cur.fetchone()["cnt"]

            # Lab stats: components per lab
            cur.execute("""
                SELECT
                    l.id AS lab_id,
                    l.name AS lab_name,
                    COUNT(c.id) AS component_count
                FROM labs l
                LEFT JOIN components c ON c.lab_id = l.id
                GROUP BY l.id, l.name
                ORDER BY l.name ASC
            """)
            lab_stats = cur.fetchall()

            # Unassigned components (no lab)
            cur.execute("""
                SELECT COUNT(*) AS cnt
                FROM components
                WHERE lab_id IS NULL
            """)
            unassigned = cur.fetchone()["cnt"]
            if unassigned > 0:
                lab_stats.append({
                    "lab_id": None,
                    "lab_name": "Unassigned",
                    "component_count": unassigned
                })

        recent_transactions = TransactionModel.get_recent(conn, limit=5)

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
    finally:
        conn.close()


# ---------------------- Routes (Protected) ---------------------- #

@app.route("/")
@login_required
def index():
    stats = get_dashboard_stats()

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT status AS _id, COUNT(*) AS count
                FROM transactions
                GROUP BY status
            """)
            trans_type_agg = cur.fetchall()
    finally:
        conn.close()

    transaction_types = [t["_id"] or "Unknown" for t in trans_type_agg]
    transaction_counts = [t["count"] for t in trans_type_agg]

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
    conn = get_db_connection()
    try:
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            location = request.form.get("location", "").strip()
            description = request.form.get("description", "").strip()

            if not name:
                flash("Lab name is required.", "danger")
            else:
                LabModel.create(conn, name, location, description)
                flash("Lab added successfully.", "success")
                return redirect(url_for("labs"))

        labs_list = LabModel.get_all(conn)
        return render_template("labs.html", labs=labs_list)
    finally:
        conn.close()


@app.route("/labs/<int:lab_id>/edit", methods=["GET", "POST"])
@login_required
def edit_lab(lab_id):
    conn = get_db_connection()
    try:
        lab = LabModel.get_by_id(conn, lab_id)
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
                LabModel.update(conn, lab_id, name, location, description)
                flash("Lab updated successfully.", "success")
                return redirect(url_for("labs"))

        return render_template("edit_lab.html", lab=lab)
    finally:
        conn.close()


@app.route("/labs/<int:lab_id>/delete", methods=["POST"])
@login_required
def delete_lab(lab_id):
    conn = get_db_connection()
    try:
        LabModel.delete(conn, lab_id)
        flash("Lab deleted.", "info")
        return redirect(url_for("labs"))
    finally:
        conn.close()


@app.route("/labs/<int:lab_id>/components")
@login_required
def lab_components(lab_id):
    conn = get_db_connection()
    try:
        lab = LabModel.get_by_id(conn, lab_id)
        if not lab:
            flash("Lab not found.", "danger")
            return redirect(url_for("labs"))

        components_list = ComponentModel.get_by_lab(conn, lab_id)
        components_list = ComponentModel.enrich_with_status(conn, components_list)

        return render_template(
            "components.html",
            components=components_list,
            selected_lab=lab,
        )
    finally:
        conn.close()


# ---------------------- Categories CRUD ---------------------- #

@app.route("/categories", methods=["GET", "POST"])
@login_required
def categories():
    conn = get_db_connection()
    try:
        labs = LabModel.get_all(conn)

        if request.method == "POST":
            lab_id = request.form.get("lab_id")
            name = request.form.get("name", "").strip()
            description = request.form.get("description", "").strip()

            if not (lab_id and name):
                flash("Lab and Category name are required.", "danger")
            else:
                CategoryModel.create(conn, name, description, lab_id)
                flash("Category added successfully.", "success")
                return redirect(url_for("categories"))

        categories_list = CategoryModel.get_all(conn)

        return render_template(
            "categories.html",
            categories=categories_list,
            labs=labs,
        )
    finally:
        conn.close()


@app.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])
@login_required
def edit_category(category_id):
    conn = get_db_connection()
    try:
        category = CategoryModel.get_by_id(conn, category_id)
        if not category:
            flash("Category not found.", "danger")
            return redirect(url_for("categories"))

        labs = LabModel.get_all(conn)

        if request.method == "POST":
            lab_id = request.form.get("lab_id")
            name = request.form.get("name", "").strip()
            description = request.form.get("description", "").strip()

            if not (lab_id and name):
                flash("Lab and Category name are required.", "danger")
            else:
                CategoryModel.update(conn, category_id, name, description, lab_id)
                flash("Category updated successfully.", "success")
                return redirect(url_for("categories"))

        return render_template(
            "edit_category.html",
            category=category,
            labs=labs,
        )
    finally:
        conn.close()


@app.route("/categories/<int:category_id>/delete", methods=["POST"])
@login_required
def delete_category(category_id):
    conn = get_db_connection()
    try:
        CategoryModel.delete(conn, category_id)
        flash("Category deleted.", "info")
        return redirect(url_for("categories"))
    finally:
        conn.close()


# ---------------------- Components CRUD ---------------------- #

@app.route("/components")
@login_required
def components():
    conn = get_db_connection()
    try:
        components_list = ComponentModel.get_all(conn)
        components_list = ComponentModel.enrich_with_status(conn, components_list)
        return render_template(
            "components.html",
            components=components_list,
            selected_lab=None,
        )
    finally:
        conn.close()


@app.route("/components/add", methods=["GET", "POST"])
@login_required
def add_component():
    conn = get_db_connection()
    try:
        labs = LabModel.get_all(conn)
        categories = CategoryModel.get_all(conn)

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
                    conn,
                    name, category_id, lab_id,
                    quantity, min_stock_level,
                    unit, description,
                    component_type=component_type,
                )
                flash("Component added successfully.", "success")
                return redirect(url_for("components"))

        return render_template(
            "add_component.html",
            labs=labs,
            categories=categories,
        )
    finally:
        conn.close()


@app.route("/components/<int:component_id>/edit", methods=["GET", "POST"])
@login_required
def edit_component(component_id):
    conn = get_db_connection()
    try:
        component = ComponentModel.get_by_id(conn, component_id)
        if not component:
            flash("Component not found.", "danger")
            return redirect(url_for("components"))

        labs = LabModel.get_all(conn)
        categories = CategoryModel.get_all(conn)

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
                    conn,
                    component_id, name, category_id, lab_id,
                    quantity, min_stock_level,
                    unit, description,
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
    finally:
        conn.close()


@app.route("/components/<int:component_id>/delete", methods=["POST"])
@login_required
def delete_component(component_id):
    conn = get_db_connection()
    try:
        ComponentModel.delete(conn, component_id)
        flash("Component deleted.", "info")
        return redirect(url_for("components"))
    finally:
        conn.close()


# ---------------------- Transactions ---------------------- #

@app.route("/transactions")
@login_required
def transactions():
    conn = get_db_connection()
    try:
        transactions_list = TransactionModel.get_all(conn)

        with conn.cursor() as cur:
            cur.execute("""
                SELECT status AS _id, COUNT(*) AS count
                FROM transactions
                GROUP BY status
            """)
            status_agg = cur.fetchall()

        status_counts = {item["_id"] or "Unknown": item["count"] for item in status_agg}

        return render_template(
            "transactions.html",
            transactions=transactions_list,
            status_counts=status_counts,
        )
    finally:
        conn.close()


@app.route("/transactions/add", methods=["GET", "POST"])
@login_required
def add_transaction():
    conn = get_db_connection()
    try:
        components = ComponentModel.get_all(conn)
        labs = LabModel.get_all(conn)

        # helper string lab_id for each component
        for c in components:
            lab_id = c.get("lab", {}).get("id") if c.get("lab") else None
            c["lab_id_str"] = str(lab_id) if lab_id is not None else ""

        preselected_component_id = request.args.get("component_id")
        preselected_type = request.args.get("transaction_type") or "issue"
        preselected_lab_id = None

        # If opened from Components "Issue/Return" quick action
        if preselected_component_id:
            comp = ComponentModel.get_by_id(conn, preselected_component_id)
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

            component = ComponentModel.get_by_id(conn, component_id)
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

            try:
                if transaction_type == "issue":
                    TransactionModel.create_issue(
                        conn, component, lab_id, campus,
                        person_name, qty, purpose, notes
                    )
                elif transaction_type == "return":
                    TransactionModel.add_return(
                        conn, component, lab_id, campus,
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

        # GET
        return render_template(
            "add_transaction.html",
            components=components,
            labs=labs,
            preselected_component_id=preselected_component_id,
            preselected_type=preselected_type,
            preselected_lab_id=preselected_lab_id,
        )
    finally:
        conn.close()


@app.route("/transactions/<int:transaction_id>/edit", methods=["GET", "POST"])
@login_required
def edit_transaction(transaction_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM transactions WHERE id = %s", (transaction_id,))
            txn = cur.fetchone()

        if not txn:
            flash("Transaction not found.", "danger")
            return redirect(url_for("transactions"))

        component = ComponentModel.get_by_id(conn, txn["component_id"])
        lab = LabModel.get_by_id(conn, txn["lab_id"]) if txn.get("lab_id") else None

        qty_issued = int(txn.get("qty_issued", 0) or 0)
        qty_returned = int(txn.get("qty_returned", 0) or 0)
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
                    conn,
                    component,
                    txn.get("lab_id"),
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
    finally:
        conn.close()


@app.route("/transactions/<int:transaction_id>/view")
@login_required
def view_transaction(transaction_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM transactions WHERE id = %s", (transaction_id,))
            txn = cur.fetchone()

        if not txn:
            flash("Transaction not found.", "danger")
            return redirect(url_for("transactions"))

        component = ComponentModel.get_by_id(conn, txn["component_id"])
        lab = LabModel.get_by_id(conn, txn["lab_id"]) if txn.get("lab_id") else None

        qty_issued = int(txn.get("qty_issued", 0) or 0)
        qty_returned = int(txn.get("qty_returned", 0) or 0)
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
    finally:
        conn.close()


# ---------------------- Reports ---------------------- #

@app.route("/reports")
@login_required
def reports():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Components by lab
            cur.execute("""
                SELECT
                    COALESCE(l.name, 'Unassigned') AS _id,
                    COUNT(c.id) AS count
                FROM components c
                LEFT JOIN labs l ON c.lab_id = l.id
                GROUP BY _id
                ORDER BY _id ASC
            """)
            components_by_lab = cur.fetchall()

            # Components by category
            cur.execute("""
                SELECT
                    COALESCE(cat.name, 'Unassigned') AS _id,
                    COUNT(c.id) AS count
                FROM components c
                LEFT JOIN categories cat ON c.category_id = cat.id
                GROUP BY _id
                ORDER BY _id ASC
            """)
            components_by_category = cur.fetchall()

            # Low stock list
            cur.execute("""
                SELECT *
                FROM components
                WHERE quantity <= min_stock_level
                ORDER BY name ASC
            """)
            low_stock_components = cur.fetchall()

            # Transaction counts by status
            cur.execute("""
                SELECT status AS _id, COUNT(*) AS count
                FROM transactions
                GROUP BY status
                ORDER BY _id ASC
            """)
            transaction_type_counts = cur.fetchall()

        return render_template(
            "reports.html",
            components_by_lab=components_by_lab,
            components_by_category=components_by_category,
            low_stock_components=low_stock_components,
            transaction_type_counts=transaction_type_counts,
        )
    finally:
        conn.close()


if __name__ == "__main__":
    app.run(debug=True)
