from bson.objectid import ObjectId
from datetime import datetime
from zoneinfo import ZoneInfo   # ✅ Python 3.9+ built-in

IST = ZoneInfo("Asia/Kolkata")  # ✅ Indian time


class LabModel:
    collection = "labs"

    @staticmethod
    def get_all(db):
        return list(db[LabModel.collection].find().sort("name", 1))

    @staticmethod
    def get_by_id(db, lab_id):
        return db[LabModel.collection].find_one({"_id": ObjectId(lab_id)})

    @staticmethod
    def create(db, name, location, description):
        doc = {
            "name": name,
            "location": location,
            "description": description,
            "created_at": datetime.now(IST)
        }
        return db[LabModel.collection].insert_one(doc)

    @staticmethod
    def update(db, lab_id, name, location, description):
        db[LabModel.collection].update_one(
            {"_id": ObjectId(lab_id)},
            {"$set": {
                "name": name,
                "location": location,
                "description": description
            }}
        )

    @staticmethod
    def delete(db, lab_id):
        db[LabModel.collection].delete_one({"_id": ObjectId(lab_id)})


class CategoryModel:
    collection = "categories"

    @staticmethod
    def get_all(db):
        """
        Returns categories enriched with:
          - lab (joined)
          - component_count (number of components under this category in that lab)
          - total_quantity (sum of quantities of those components)
        """
        pipeline = [
            {
                "$lookup": {
                    "from": "labs",
                    "localField": "lab_id",
                    "foreignField": "_id",
                    "as": "lab"
                }
            },
            {"$unwind": {"path": "$lab", "preserveNullAndEmptyArrays": True}},
            {
                "$lookup": {
                    "from": "components",
                    "let": {"catId": "$_id", "labId": "$lab_id"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": ["$category_id", "$$catId"]},
                                        {"$eq": ["$lab_id", "$$labId"]}
                                    ]
                                }
                            }
                        }
                    ],
                    "as": "components_in_cat"
                }
            },
            {
                "$addFields": {
                    "component_count": {"$size": "$components_in_cat"},
                    "total_quantity": {"$sum": "$components_in_cat.quantity"}
                }
            },
            {"$project": {"components_in_cat": 0}},
            {"$sort": {"lab.name": 1, "name": 1}}
        ]
        return list(db[CategoryModel.collection].aggregate(pipeline))

    @staticmethod
    def get_by_id(db, category_id):
        return db[CategoryModel.collection].find_one({"_id": ObjectId(category_id)})

    @staticmethod
    def create(db, name, description, lab_id):
        doc = {
            "name": name,
            "description": description,
            "lab_id": ObjectId(lab_id) if lab_id else None,
            "created_at": datetime.now(IST)
        }
        return db[CategoryModel.collection].insert_one(doc)

    @staticmethod
    def update(db, category_id, name, description, lab_id):
        db[CategoryModel.collection].update_one(
            {"_id": ObjectId(category_id)},
            {"$set": {
                "name": name,
                "description": description,
                "lab_id": ObjectId(lab_id) if lab_id else None
            }}
        )

    @staticmethod
    def delete(db, category_id):
        db[CategoryModel.collection].delete_one({"_id": ObjectId(category_id)})


class ComponentModel:
    collection = "components"

    @staticmethod
    def get_all(db):
        pipeline = [
            {
                "$lookup": {
                    "from": "categories",
                    "localField": "category_id",
                    "foreignField": "_id",
                    "as": "category"
                }
            },
            {"$unwind": {"path": "$category", "preserveNullAndEmptyArrays": True}},
            {
                "$lookup": {
                    "from": "labs",
                    "localField": "lab_id",
                    "foreignField": "_id",
                    "as": "lab"
                }
            },
            {"$unwind": {"path": "$lab", "preserveNullAndEmptyArrays": True}},
            {"$sort": {"name": 1}}
        ]
        return list(db[ComponentModel.collection].aggregate(pipeline))

    @staticmethod
    def get_by_lab(db, lab_id):
        """
        Return components only for a specific lab_id,
        enriched with category + lab like get_all().
        """
        pipeline = [
            {
                "$match": {
                    "lab_id": ObjectId(lab_id)
                }
            },
            {
                "$lookup": {
                    "from": "categories",
                    "localField": "category_id",
                    "foreignField": "_id",
                    "as": "category"
                }
            },
            {"$unwind": {"path": "$category", "preserveNullAndEmptyArrays": True}},
            {
                "$lookup": {
                    "from": "labs",
                    "localField": "lab_id",
                    "foreignField": "_id",
                    "as": "lab"
                }
            },
            {"$unwind": {"path": "$lab", "preserveNullAndEmptyArrays": True}},
            {"$sort": {"name": 1}}
        ]
        return list(db[ComponentModel.collection].aggregate(pipeline))

    @staticmethod
    def get_by_id(db, component_id):
        return db[ComponentModel.collection].find_one({"_id": ObjectId(component_id)})

    @staticmethod
    def create(
        db, name, category_id, lab_id, quantity,
        min_stock_level, unit, description,
        component_type="Other"
    ):
        now = datetime.now(IST)
        doc = {
            "name": name,
            "category_id": ObjectId(category_id),
            "lab_id": ObjectId(lab_id),
            "quantity": quantity,
            "min_stock_level": min_stock_level,
            "unit": unit,
            "description": description,
            "component_type": component_type or "Other",
            "date_added": now,
            "last_updated": now
        }
        return db[ComponentModel.collection].insert_one(doc)

    @staticmethod
    def update(
        db, component_id, name, category_id, lab_id,
        quantity, min_stock_level, unit, description,
        component_type="Other"
    ):
        db[ComponentModel.collection].update_one(
            {"_id": ObjectId(component_id)},
            {"$set": {
                "name": name,
                "category_id": ObjectId(category_id),
                "lab_id": ObjectId(lab_id),
                "quantity": quantity,
                "min_stock_level": min_stock_level,
                "unit": unit,
                "description": description,
                "component_type": component_type or "Other",
                "last_updated": datetime.now(IST)
            }}
        )

    @staticmethod
    def delete(db, component_id):
        db[ComponentModel.collection].delete_one({"_id": ObjectId(component_id)})

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
    collection = "transactions"

    @staticmethod
    def get_all(db):
        """
        Each document = one logical transaction:
          - qty_issued
          - qty_returned
          - pending_qty
          - status: Issued / Partially Returned / Completed
        """
        pipeline = [
            {
                "$lookup": {
                    "from": "components",
                    "localField": "component_id",
                    "foreignField": "_id",
                    "as": "component"
                }
            },
            {"$unwind": {"path": "$component", "preserveNullAndEmptyArrays": True}},
            {
                "$lookup": {
                    "from": "labs",
                    "localField": "lab_id",
                    "foreignField": "_id",
                    "as": "lab"
                }
            },
            {"$unwind": {"path": "$lab", "preserveNullAndEmptyArrays": True}},
            {"$sort": {"issue_date": -1}}
        ]
        return list(db[TransactionModel.collection].aggregate(pipeline))

    @staticmethod
    def get_recent(db, limit=5):
        return list(
            db[TransactionModel.collection]
            .find()
            .sort("issue_date", -1)
            .limit(limit)
        )

    @staticmethod
    def _find_open_transaction(db, component, lab_id, campus, person_name, purpose):
        """Find existing open (not completed) transaction for same context."""
        query = {
            "component_id": component["_id"],
            "lab_id": ObjectId(lab_id) if lab_id else None,
            "campus": campus,
            "person_name": person_name,
            "purpose": purpose,
            "status": {"$in": ["Issued", "Partially Returned"]}
        }
        return db[TransactionModel.collection].find_one(query)

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
        lab_oid = ObjectId(lab_id) if lab_id else None
        campus = campus or None

        existing = TransactionModel._find_open_transaction(
            db, component, lab_id, campus, person_name, purpose
        )

        if existing:
            new_issued = int(existing.get("qty_issued", 0)) + qty
            qty_returned = int(existing.get("qty_returned", 0))
            pending = new_issued - qty_returned
            status = "Issued" if qty_returned == 0 else (
                "Completed" if pending <= 0 else "Partially Returned"
            )

            db[TransactionModel.collection].update_one(
                {"_id": existing["_id"]},
                {"$set": {
                    "qty_issued": new_issued,
                    "pending_qty": pending,
                    "status": status,
                    "quantity_before": current_stock,
                    "quantity_after": quantity_after,
                    "last_action": "issue",
                    "transaction_quantity": qty,
                    "date": now,
                    "last_updated": now,
                    "notes": notes or existing.get("notes", "")
                }}
            )
        else:
            doc = {
                "component_id": component["_id"],
                "lab_id": lab_oid,
                "campus": campus,
                "person_name": person_name,
                "purpose": purpose,
                "qty_issued": qty,
                "qty_returned": 0,
                "pending_qty": qty,
                "status": "Issued",  # full pending
                "issue_date": now,
                "date": now,         # last action date
                "quantity_before": current_stock,
                "quantity_after": quantity_after,
                "transaction_quantity": qty,
                "last_action": "issue",
                "notes": notes,
                "last_updated": now
            }
            db[TransactionModel.collection].insert_one(doc)

        # Update component stock
        db["components"].update_one(
            {"_id": component["_id"]},
            {"$set": {
                "quantity": quantity_after,
                "last_updated": now
            }}
        )

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
        lab_oid = ObjectId(lab_id) if lab_id else None
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

        db[TransactionModel.collection].update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "qty_returned": new_returned,
                "pending_qty": new_pending,
                "status": status,
                "quantity_before": current_stock,
                "quantity_after": quantity_after,
                "last_action": "return",
                "transaction_quantity": qty,
                "date": now,           # last action date
                "last_updated": now,
                "notes": (existing.get("notes") or "") + (
                    f"\nReturn: {notes}" if notes else ""
                )
            }}
        )

        # Update stock back into component
        db["components"].update_one(
            {"_id": component["_id"]},
            {"$set": {
                "quantity": quantity_after,
                "last_updated": now
            }}
        )
