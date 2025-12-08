from datetime import datetime
from zoneinfo import ZoneInfo   # Python 3.9+
# All methods take a plain MySQL connection object as `db`

IST = ZoneInfo("Asia/Kolkata")


class LabModel:
    @staticmethod
    def get_all(db):
        with db.cursor() as cur:
            cur.execute("""
                SELECT id, name, location, description, created_at
                FROM labs
                ORDER BY name ASC
            """)
            return cur.fetchall()

    @staticmethod
    def get_by_id(db, lab_id):
        with db.cursor() as cur:
            cur.execute("""
                SELECT id, name, location, description, created_at
                FROM labs
                WHERE id = %s
            """, (lab_id,))
            return cur.fetchone()

    @staticmethod
    def create(db, name, location, description):
        now = datetime.now(IST)
        with db.cursor() as cur:
            cur.execute("""
                INSERT INTO labs (name, location, description, created_at)
                VALUES (%s, %s, %s, %s)
            """, (name, location, description, now))
            db.commit()
            return cur.lastrowid

    @staticmethod
    def update(db, lab_id, name, location, description):
        with db.cursor() as cur:
            cur.execute("""
                UPDATE labs
                SET name = %s,
                    location = %s,
                    description = %s
                WHERE id = %s
            """, (name, location, description, lab_id))
            db.commit()

    @staticmethod
    def delete(db, lab_id):
        with db.cursor() as cur:
            cur.execute("DELETE FROM labs WHERE id = %s", (lab_id,))
            db.commit()


class CategoryModel:
    @staticmethod
    def get_all(db):
        """
        Returns categories enriched with:
          - lab_name
          - component_count
          - total_quantity
        """
        with db.cursor() as cur:
            cur.execute("""
                SELECT
                    c.id,
                    c.name,
                    c.description,
                    c.lab_id,
                    c.created_at,
                    l.name AS lab_name,
                    COUNT(co.id) AS component_count,
                    COALESCE(SUM(co.quantity), 0) AS total_quantity
                FROM categories c
                LEFT JOIN labs l ON c.lab_id = l.id
                LEFT JOIN components co
                    ON co.category_id = c.id
                    AND co.lab_id = c.lab_id
                GROUP BY c.id, c.name, c.description, c.lab_id, c.created_at, l.name
                ORDER BY lab_name ASC, c.name ASC
            """)
            return cur.fetchall()

    @staticmethod
    def get_by_id(db, category_id):
        with db.cursor() as cur:
            cur.execute("""
                SELECT id, name, description, lab_id, created_at
                FROM categories
                WHERE id = %s
            """, (category_id,))
            return cur.fetchone()

    @staticmethod
    def create(db, name, description, lab_id):
        now = datetime.now(IST)
        with db.cursor() as cur:
            cur.execute("""
                INSERT INTO categories (name, description, lab_id, created_at)
                VALUES (%s, %s, %s, %s)
            """, (name, description, lab_id, now))
            db.commit()
            return cur.lastrowid

    @staticmethod
    def update(db, category_id, name, description, lab_id):
        with db.cursor() as cur:
            cur.execute("""
                UPDATE categories
                SET name = %s,
                    description = %s,
                    lab_id = %s
                WHERE id = %s
            """, (name, description, lab_id, category_id))
            db.commit()

    @staticmethod
    def delete(db, category_id):
        with db.cursor() as cur:
            cur.execute("DELETE FROM categories WHERE id = %s", (category_id,))
            db.commit()


class ComponentModel:
    @staticmethod
    def get_all(db):
        """
        Returns components with joined category + lab
        and shapes them similar to original Mongo structure:
        component['category']['name'], component['lab']['name']
        """
        with db.cursor() as cur:
            cur.execute("""
                SELECT
                    co.id,
                    co.name,
                    co.category_id,
                    co.lab_id,
                    co.quantity,
                    co.min_stock_level,
                    co.unit,
                    co.description,
                    co.component_type,
                    co.date_added,
                    co.last_updated,
                    cat.name AS category_name,
                    l.name AS lab_name
                FROM components co
                LEFT JOIN categories cat ON co.category_id = cat.id
                LEFT JOIN labs l ON co.lab_id = l.id
                ORDER BY co.name ASC
            """)
            rows = cur.fetchall()

        # Shape to mimic previous nested structure
        components = []
        for r in rows:
            comp = dict(r)
            comp["category"] = {
                "id": r["category_id"],
                "name": r["category_name"]
            } if r["category_id"] else None
            comp["lab"] = {
                "id": r["lab_id"],
                "name": r["lab_name"]
            } if r["lab_id"] else None
            components.append(comp)

        return components

    @staticmethod
    def get_by_lab(db, lab_id):
        with db.cursor() as cur:
            cur.execute("""
                SELECT
                    co.id,
                    co.name,
                    co.category_id,
                    co.lab_id,
                    co.quantity,
                    co.min_stock_level,
                    co.unit,
                    co.description,
                    co.component_type,
                    co.date_added,
                    co.last_updated,
                    cat.name AS category_name,
                    l.name AS lab_name
                FROM components co
                LEFT JOIN categories cat ON co.category_id = cat.id
                LEFT JOIN labs l ON co.lab_id = l.id
                WHERE co.lab_id = %s
                ORDER BY co.name ASC
            """, (lab_id,))
            rows = cur.fetchall()

        components = []
        for r in rows:
            comp = dict(r)
            comp["category"] = {
                "id": r["category_id"],
                "name": r["category_name"]
            } if r["category_id"] else None
            comp["lab"] = {
                "id": r["lab_id"],
                "name": r["lab_name"]
            } if r["lab_id"] else None
            components.append(comp)

        return components

    @staticmethod
    def get_by_id(db, component_id):
        with db.cursor() as cur:
            cur.execute("""
                SELECT
                    id,
                    name,
                    category_id,
                    lab_id,
                    quantity,
                    min_stock_level,
                    unit,
                    description,
                    component_type,
                    date_added,
                    last_updated
                FROM components
                WHERE id = %s
            """, (component_id,))
            return cur.fetchone()

    @staticmethod
    def create(
        db, name, category_id, lab_id, quantity,
        min_stock_level, unit, description,
        component_type="Other"
    ):
        now = datetime.now(IST)
        with db.cursor() as cur:
            cur.execute("""
                INSERT INTO components (
                    name, category_id, lab_id, quantity, min_stock_level,
                    unit, description, component_type, date_added, last_updated
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                name, category_id, lab_id, quantity, min_stock_level,
                unit, description, component_type or "Other", now, now
            ))
            db.commit()
            return cur.lastrowid

    @staticmethod
    def update(
        db, component_id, name, category_id, lab_id,
        quantity, min_stock_level, unit, description,
        component_type="Other"
    ):
        now = datetime.now(IST)
        with db.cursor() as cur:
            cur.execute("""
                UPDATE components
                SET name = %s,
                    category_id = %s,
                    lab_id = %s,
                    quantity = %s,
                    min_stock_level = %s,
                    unit = %s,
                    description = %s,
                    component_type = %s,
                    last_updated = %s
                WHERE id = %s
            """, (
                name, category_id, lab_id, quantity, min_stock_level,
                unit, description, component_type or "Other", now, component_id
            ))
            db.commit()

    @staticmethod
    def delete(db, component_id):
        with db.cursor() as cur:
            cur.execute("DELETE FROM components WHERE id = %s", (component_id,))
            db.commit()

    @staticmethod
    def enrich_with_status(db, components):
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
    @staticmethod
    def get_all(db):
        """
        Each row = one logical transaction:
          - qty_issued
          - qty_returned
          - pending_qty
          - status
        plus joined component + lab.
        """
        with db.cursor() as cur:
            cur.execute("""
                SELECT
                    t.*,
                    c.name AS component_name,
                    c.unit AS component_unit,
                    l.name AS lab_name
                FROM transactions t
                LEFT JOIN components c ON t.component_id = c.id
                LEFT JOIN labs l ON t.lab_id = l.id
                ORDER BY t.issue_date DESC
            """)
            rows = cur.fetchall()

        # Shape a bit like previous Mongo version
        txns = []
        for r in rows:
            txn = dict(r)
            txn["component"] = {
                "id": r["component_id"],
                "name": r["component_name"],
                "unit": r["component_unit"],
            } if r["component_id"] else None
            txn["lab"] = {
                "id": r["lab_id"],
                "name": r["lab_name"],
            } if r["lab_id"] else None
            txns.append(txn)

        return txns

    @staticmethod
    def get_recent(db, limit=5):
        with db.cursor() as cur:
            cur.execute("""
                SELECT *
                FROM transactions
                ORDER BY date DESC
                LIMIT %s
            """, (limit,))
            return cur.fetchall()

    @staticmethod
    def _find_open_transaction(db, component, lab_id, campus, person_name, purpose):
        """
        Find existing open (not completed) transaction for same context.
        """
        conditions = ["component_id = %s", "person_name = %s", "purpose = %s",
                      "status IN ('Issued', 'Partially Returned')"]
        params = [component["id"], person_name, purpose]

        if lab_id:
            conditions.append("lab_id = %s")
            params.append(lab_id)
        else:
            conditions.append("lab_id IS NULL")

        if campus:
            conditions.append("campus = %s")
            params.append(campus)
        else:
            conditions.append("campus IS NULL")

        sql = f"""
            SELECT *
            FROM transactions
            WHERE {" AND ".join(conditions)}
            LIMIT 1
        """
        with db.cursor() as cur:
            cur.execute(sql, tuple(params))
            return cur.fetchone()

    @staticmethod
    def create_issue(
        db, component, lab_id, campus,
        person_name, qty, purpose, notes
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
        campus = campus or None

        existing = TransactionModel._find_open_transaction(
            db, component, lab_id, campus, person_name, purpose
        )

        if existing:
            new_issued = int(existing.get("qty_issued", 0) or 0) + qty
            qty_returned = int(existing.get("qty_returned", 0) or 0)
            pending = new_issued - qty_returned
            if qty_returned == 0:
                status = "Issued"
            else:
                status = "Completed" if pending <= 0 else "Partially Returned"

            with db.cursor() as cur:
                cur.execute("""
                    UPDATE transactions
                    SET qty_issued = %s,
                        pending_qty = %s,
                        status = %s,
                        quantity_before = %s,
                        quantity_after = %s,
                        last_action = 'issue',
                        transaction_quantity = %s,
                        date = %s,
                        last_updated = %s,
                        notes = IFNULL(%s, notes)
                    WHERE id = %s
                """, (
                    new_issued, pending, status,
                    current_stock, quantity_after,
                    qty, now, now,
                    notes or existing.get("notes", ""),
                    existing["id"]
                ))
                db.commit()
        else:
            with db.cursor() as cur:
                cur.execute("""
                    INSERT INTO transactions (
                        component_id, lab_id, campus,
                        person_name, purpose,
                        qty_issued, qty_returned, pending_qty,
                        status, issue_date, date,
                        quantity_before, quantity_after,
                        transaction_quantity, last_action,
                        notes, last_updated
                    )
                    VALUES (%s, %s, %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s,
                            %s, %s,
                            %s, %s,
                            %s, %s)
                """, (
                    component["id"], lab_id, campus,
                    person_name, purpose,
                    qty, 0, qty,
                    "Issued", now, now,
                    current_stock, quantity_after,
                    qty, "issue",
                    notes, now
                ))
                db.commit()

        # Update component stock
        with db.cursor() as cur:
            cur.execute("""
                UPDATE components
                SET quantity = %s,
                    last_updated = %s
                WHERE id = %s
            """, (quantity_after, now, component["id"]))
            db.commit()

    @staticmethod
    def add_return(
        db, component, lab_id, campus,
        person_name, qty, purpose, notes
    ):
        """
        RETURN: update qty_returned on SAME row.
        Component stock increases.
        """
        now = datetime.now(IST)
        current_stock = int(component.get("quantity", 0) or 0)
        campus = campus or None

        existing = TransactionModel._find_open_transaction(
            db, component, lab_id, campus, person_name, purpose
        )

        if not existing:
            raise ValueError(
                "No matching issued transaction found to return against "
                "(check Component / Lab / Campus / Person / Purpose)."
            )

        qty_issued = int(existing.get("qty_issued", 0) or 0)
        qty_returned = int(existing.get("qty_returned", 0) or 0)
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

        notes_combined = (existing.get("notes") or "")
        if notes:
            notes_combined = (notes_combined + "\nReturn: " + notes).strip()

        with db.cursor() as cur:
            cur.execute("""
                UPDATE transactions
                SET qty_returned = %s,
                    pending_qty = %s,
                    status = %s,
                    quantity_before = %s,
                    quantity_after = %s,
                    last_action = 'return',
                    transaction_quantity = %s,
                    date = %s,
                    last_updated = %s,
                    notes = %s
                WHERE id = %s
            """, (
                new_returned, new_pending, status,
                current_stock, quantity_after,
                qty, now, now,
                notes_combined,
                existing["id"]
            ))
            db.commit()

        # Update component stock
        with db.cursor() as cur:
            cur.execute("""
                UPDATE components
                SET quantity = %s,
                    last_updated = %s
                WHERE id = %s
            """, (quantity_after, now, component["id"]))
            db.commit()
