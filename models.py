from datetime import datetime
from zoneinfo import ZoneInfo   # Python 3.9+

IST = ZoneInfo("Asia/Kolkata")  # Indian time


class LabModel:
    table = "labs"

    @staticmethod
    def get_all(db):
        with db.cursor() as cur:
            cur.execute(
                f"SELECT id, name, location, description, created_at "
                f"FROM {LabModel.table} ORDER BY name ASC"
            )
            rows = cur.fetchall()
        for r in rows:
            r["_id"] = r["id"]
        return rows

    @staticmethod
    def get_by_id(db, lab_id):
        with db.cursor() as cur:
            cur.execute(
                f"SELECT id, name, location, description, created_at "
                f"FROM {LabModel.table} WHERE id = %s",
                (int(lab_id),),
            )
            lab = cur.fetchone()
        if lab:
            lab["_id"] = lab["id"]
        return lab

    @staticmethod
    def create(db, name, location, description):
        now = datetime.now(IST)
        with db.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {LabModel.table}
                    (name, location, description, created_at)
                VALUES (%s, %s, %s, %s)
                """,
                (name, location, description, now),
            )

    @staticmethod
    def update(db, lab_id, name, location, description):
        with db.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {LabModel.table}
                SET name=%s, location=%s, description=%s
                WHERE id=%s
                """,
                (name, location, description, int(lab_id)),
            )

    @staticmethod
    def delete(db, lab_id):
        with db.cursor() as cur:
            cur.execute(
                f"DELETE FROM {LabModel.table} WHERE id=%s",
                (int(lab_id),),
            )


class CategoryModel:
    table = "categories"

    @staticmethod
    def get_all(db):
        """
        Returns categories enriched with:
          - lab (joined)
          - component_count (number of components under this category in that lab)
          - total_quantity (sum of quantities of those components)
        """
        sql = """
        SELECT
            c.id,
            c.name,
            c.description,
            c.lab_id,
            c.created_at,
            l.name AS lab_name,
            COUNT(comp.id) AS component_count,
            COALESCE(SUM(comp.quantity), 0) AS total_quantity
        FROM categories c
        LEFT JOIN labs l ON c.lab_id = l.id
        LEFT JOIN components comp
            ON comp.category_id = c.id
           AND comp.lab_id = c.lab_id
        GROUP BY
            c.id, c.name, c.description, c.lab_id, c.created_at, l.name
        ORDER BY
            l.name ASC, c.name ASC
        """
        with db.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()

        for r in rows:
            r["_id"] = r["id"]
            r["lab"] = {
                "_id": r["lab_id"],
                "name": r["lab_name"],
            }
        return rows

    @staticmethod
    def get_by_id(db, category_id):
        with db.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, name, description, lab_id, created_at
                FROM {CategoryModel.table}
                WHERE id = %s
                """,
                (int(category_id),),
            )
            cat = cur.fetchone()
        if cat:
            cat["_id"] = cat["id"]
        return cat

    @staticmethod
    def create(db, name, description, lab_id):
        now = datetime.now(IST)
        lab_id_int = int(lab_id) if lab_id else None
        with db.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {CategoryModel.table}
                    (name, description, lab_id, created_at)
                VALUES (%s, %s, %s, %s)
                """,
                (name, description, lab_id_int, now),
            )

    @staticmethod
    def update(db, category_id, name, description, lab_id):
        lab_id_int = int(lab_id) if lab_id else None
        with db.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {CategoryModel.table}
                SET name=%s, description=%s, lab_id=%s
                WHERE id=%s
                """,
                (name, description, lab_id_int, int(category_id)),
            )

    @staticmethod
    def delete(db, category_id):
        with db.cursor() as cur:
            cur.execute(
                f"DELETE FROM {CategoryModel.table} WHERE id=%s",
                (int(category_id),),
            )


class ComponentModel:
    table = "components"

    @staticmethod
    def _attach_relations(rows):
        for r in rows:
            r["_id"] = r["id"]
            r["category"] = {
                "_id": r.get("category_id"),
                "name": r.get("category_name"),
            }
            r["lab"] = {
                "_id": r.get("lab_id"),
                "name": r.get("lab_name"),
            }
        return rows

    @staticmethod
    def get_all(db):
        sql = """
        SELECT
            c.id,
            c.name,
            c.category_id,
            c.lab_id,
            c.quantity,
            c.min_stock_level,
            c.unit,
            c.description,
            c.component_type,
            c.date_added,
            c.last_updated,
            cat.name AS category_name,
            l.name AS lab_name
        FROM components c
        LEFT JOIN categories cat ON c.category_id = cat.id
        LEFT JOIN labs l ON c.lab_id = l.id
        ORDER BY c.name ASC
        """
        with db.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
        return ComponentModel._attach_relations(rows)

    @staticmethod
    def get_by_lab(db, lab_id):
        sql = """
        SELECT
            c.id,
            c.name,
            c.category_id,
            c.lab_id,
            c.quantity,
            c.min_stock_level,
            c.unit,
            c.description,
            c.component_type,
            c.date_added,
            c.last_updated,
            cat.name AS category_name,
            l.name AS lab_name
        FROM components c
        LEFT JOIN categories cat ON c.category_id = cat.id
        LEFT JOIN labs l ON c.lab_id = l.id
        WHERE c.lab_id = %s
        ORDER BY c.name ASC
        """
        with db.cursor() as cur:
            cur.execute(sql, (int(lab_id),))
            rows = cur.fetchall()
        return ComponentModel._attach_relations(rows)

    @staticmethod
    def get_by_id(db, component_id):
        sql = """
        SELECT
            c.id,
            c.name,
            c.category_id,
            c.lab_id,
            c.quantity,
            c.min_stock_level,
            c.unit,
            c.description,
            c.component_type,
            c.date_added,
            c.last_updated,
            cat.name AS category_name,
            l.name AS lab_name
        FROM components c
        LEFT JOIN categories cat ON c.category_id = cat.id
        LEFT JOIN labs l ON c.lab_id = l.id
        WHERE c.id = %s
        """
        with db.cursor() as cur:
            cur.execute(sql, (int(component_id),))
            row = cur.fetchone()
        if row:
            ComponentModel._attach_relations([row])
            return row
        return None

    @staticmethod
    def create(
        db,
        name,
        category_id,
        lab_id,
        quantity,
        min_stock_level,
        unit,
        description,
        component_type="Other",
    ):
        now = datetime.now(IST)
        with db.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {ComponentModel.table}
                    (name, category_id, lab_id, quantity,
                     min_stock_level, unit, description,
                     component_type, date_added, last_updated)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    name,
                    int(category_id),
                    int(lab_id),
                    quantity,
                    min_stock_level,
                    unit,
                    description,
                    component_type or "Other",
                    now,
                    now,
                ),
            )

    @staticmethod
    def update(
        db,
        component_id,
        name,
        category_id,
        lab_id,
        quantity,
        min_stock_level,
        unit,
        description,
        component_type="Other",
    ):
        now = datetime.now(IST)
        with db.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {ComponentModel.table}
                SET
                    name=%s,
                    category_id=%s,
                    lab_id=%s,
                    quantity=%s,
                    min_stock_level=%s,
                    unit=%s,
                    description=%s,
                    component_type=%s,
                    last_updated=%s
                WHERE id=%s
                """,
                (
                    name,
                    int(category_id),
                    int(lab_id),
                    quantity,
                    min_stock_level,
                    unit,
                    description,
                    component_type or "Other",
                    now,
                    int(component_id),
                ),
            )

    @staticmethod
    def delete(db, component_id):
        with db.cursor() as cur:
            cur.execute(
                f"DELETE FROM {ComponentModel.table} WHERE id=%s",
                (int(component_id),),
            )

    @staticmethod
    def enrich_with_status(db, components):
        # db is unused, kept for compatibility with old calls
        for c in components:
            qty = c.get("quantity", 0) or 0
            min_stock = c.get("min_stock_level", 0) or 0

            if qty <= 0:
                stock_state = "Out of Stock"
                stock_class = "out"
            elif qty <= min_stock:
                stock_state = "Low Stock"
                stock_class = "low"
            else:
                stock_state = "In Stock"
                stock_class = "instock"

            c["stock_state"] = stock_state
            c["stock_state_class"] = stock_class
            c["status_label"] = stock_state
            c["status_detail"] = ""

        return components


class TransactionModel:
    table = "transactions"

    @staticmethod
    def get_all(db):
        """
        Each row = one logical transaction:
          - qty_issued
          - qty_returned
          - pending_qty
          - status: Issued / Partially Returned / Completed
        """
        sql = """
        SELECT
            t.*,
            c.name AS component_name,
            l.name AS lab_name
        FROM transactions t
        LEFT JOIN components c ON t.component_id = c.id
        LEFT JOIN labs l ON t.lab_id = l.id
        ORDER BY t.issue_date DESC
        """
        with db.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()

        for r in rows:
            r["_id"] = r["id"]
            r["component"] = {
                "_id": r.get("component_id"),
                "name": r.get("component_name"),
            }
            r["lab"] = {
                "_id": r.get("lab_id"),
                "name": r.get("lab_name"),
            }
        return rows

    @staticmethod
    def get_recent(db, limit=5):
        sql = f"""
        SELECT
            id,
            person_name,
            last_action,
            transaction_quantity,
            quantity_before,
            quantity_after,
            date
        FROM {TransactionModel.table}
        ORDER BY date DESC
        LIMIT %s
        """
        with db.cursor() as cur:
            cur.execute(sql, (int(limit),))
            rows = cur.fetchall()
        for r in rows:
            r["_id"] = r["id"]
        return rows

    @staticmethod
    def get_by_id(db, transaction_id):
        sql = """
        SELECT
            t.*,
            c.name AS component_name,
            l.name AS lab_name
        FROM transactions t
        LEFT JOIN components c ON t.component_id = c.id
        LEFT JOIN labs l ON t.lab_id = l.id
        WHERE t.id = %s
        """
        with db.cursor() as cur:
            cur.execute(sql, (int(transaction_id),))
            row = cur.fetchone()
        if row:
            row["_id"] = row["id"]
            row["component"] = {
                "_id": row.get("component_id"),
                "name": row.get("component_name"),
            }
            row["lab"] = {
                "_id": row.get("lab_id"),
                "name": row.get("lab_name"),
            }
        return row

    @staticmethod
    def _find_open_transaction(db, component, lab_id, campus, person_name, purpose):
        """Find existing open (not completed) transaction for same context."""
        comp_id = component["_id"]
        lab_val = int(lab_id) if lab_id else None
        campus_val = campus or None

        sql = f"""
        SELECT *
        FROM {TransactionModel.table}
        WHERE component_id = %s
          AND (lab_id = %s OR (lab_id IS NULL AND %s IS NULL))
          AND (campus = %s OR (campus IS NULL AND %s IS NULL))
          AND person_name = %s
          AND purpose = %s
          AND status IN ('Issued', 'Partially Returned')
        ORDER BY issue_date DESC
        LIMIT 1
        """
        params = (
            comp_id,
            lab_val,
            lab_val,
            campus_val,
            campus_val,
            person_name,
            purpose,
        )
        with db.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        return row

    @staticmethod
    def create_issue(
        db,
        component,
        lab_id,
        campus,
        person_name,
        qty,
        purpose,
        notes,
    ):
        """
        ISSUE: increase qty_issued on an existing row OR create a new row.
        Component stock decreases.
        """
        now = datetime.now(IST)
        current_stock = int(component.get("quantity", 0) or 0)

        if qty > current_stock:
            raise ValueError(
                f"Cannot issue {qty} units. Only {current_stock} available in stock."
            )

        quantity_after = current_stock - qty
        lab_oid = int(lab_id) if lab_id else None
        campus = campus or None

        existing = TransactionModel._find_open_transaction(
            db, component, lab_id, campus, person_name, purpose
        )

        if existing:
            new_issued = int(existing.get("qty_issued", 0)) + qty
            qty_returned = int(existing.get("qty_returned", 0))
            pending = new_issued - qty_returned
            status = (
                "Issued"
                if qty_returned == 0
                else ("Completed" if pending <= 0 else "Partially Returned")
            )

            with db.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE {TransactionModel.table}
                    SET
                        qty_issued=%s,
                        pending_qty=%s,
                        status=%s,
                        quantity_before=%s,
                        quantity_after=%s,
                        last_action=%s,
                        transaction_quantity=%s,
                        date=%s,
                        last_updated=%s,
                        notes=%s
                    WHERE id=%s
                    """,
                    (
                        new_issued,
                        pending,
                        status,
                        current_stock,
                        quantity_after,
                        "issue",
                        qty,
                        now,
                        now,
                        notes or existing.get("notes", ""),
                        existing["id"],
                    ),
                )
        else:
            with db.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {TransactionModel.table}
                        (component_id, lab_id, campus, person_name, purpose,
                         qty_issued, qty_returned, pending_qty, status,
                         issue_date, date,
                         quantity_before, quantity_after,
                         transaction_quantity, last_action, notes,
                         last_updated)
                    VALUES
                        (%s, %s, %s, %s, %s,
                         %s, %s, %s, %s,
                         %s, %s,
                         %s, %s,
                         %s, %s, %s,
                         %s)
                    """,
                    (
                        component["_id"],
                        lab_oid,
                        campus,
                        person_name,
                        purpose,
                        qty,
                        0,
                        qty,
                        "Issued",
                        now,
                        now,
                        current_stock,
                        quantity_after,
                        qty,
                        "issue",
                        notes,
                        now,
                    ),
                )

        # Update component stock
        with db.cursor() as cur:
            cur.execute(
                """
                UPDATE components
                SET quantity=%s, last_updated=%s
                WHERE id=%s
                """,
                (quantity_after, now, component["_id"]),
            )

    @staticmethod
    def add_return(
        db,
        component,
        lab_id,
        campus,
        person_name,
        qty,
        purpose,
        notes,
    ):
        """
        RETURN: update qty_returned on SAME row.
        Component stock increases.
        """
        now = datetime.now(IST)
        current_stock = int(component.get("quantity", 0) or 0)
        lab_oid = int(lab_id) if lab_id else None
        campus = campus or None

        existing = TransactionModel._find_open_transaction(
            db, component, lab_id, campus, person_name, purpose
        )

        if not existing:
            raise ValueError(
                "No matching issued transaction found to return against "
                "(check Component / Lab / Campus / Person / Purpose)."
            )

        qty_issued = int(existing.get("qty_issued", 0))
        qty_returned = int(existing.get("qty_returned", 0))
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

        combined_notes = (existing.get("notes") or "") + (
            f"\nReturn: {notes}" if notes else ""
        )

        with db.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {TransactionModel.table}
                SET
                    qty_returned=%s,
                    pending_qty=%s,
                    status=%s,
                    quantity_before=%s,
                    quantity_after=%s,
                    last_action=%s,
                    transaction_quantity=%s,
                    date=%s,
                    last_updated=%s,
                    notes=%s
                WHERE id=%s
                """,
                (
                    new_returned,
                    new_pending,
                    status,
                    current_stock,
                    quantity_after,
                    "return",
                    qty,
                    now,
                    now,
                    combined_notes,
                    existing["id"],
                ),
            )

        # Update stock back into component
        with db.cursor() as cur:
            cur.execute(
                """
                UPDATE components
                SET quantity=%s, last_updated=%s
                WHERE id=%s
                """,
                (quantity_after, now, component["_id"]),
            )
