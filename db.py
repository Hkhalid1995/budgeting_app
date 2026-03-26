import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "budget_data.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL UNIQUE,
            name TEXT,
            monthly_income REAL,
            currency TEXT DEFAULT 'PKR',
            created_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            name TEXT,
            target_amount REAL,
            deadline TEXT,
            priority INTEGER DEFAULT 1
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS budget_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            name TEXT,
            monthly_limit REAL,
            icon TEXT DEFAULT 'folder'
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            category_id INTEGER,
            amount REAL,
            note TEXT,
            date TEXT,
            flagged INTEGER DEFAULT 0,
            receipt_text TEXT,
            FOREIGN KEY (category_id) REFERENCES budget_categories(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            category_id INTEGER,
            message TEXT,
            triggered_at TEXT,
            dismissed INTEGER DEFAULT 0,
            FOREIGN KEY (category_id) REFERENCES budget_categories(id)
        )
    """)
    conn.commit()
    conn.close()


def save_profile(user_id, name, monthly_income, currency="PKR"):
    conn = get_conn()
    conn.execute(
        """INSERT INTO profile (user_id, name, monthly_income, currency, created_at)
           VALUES (?,?,?,?,?)
           ON CONFLICT(user_id) DO UPDATE SET
               name=excluded.name,
               monthly_income=excluded.monthly_income,
               currency=excluded.currency""",
        (user_id, name, monthly_income, currency, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_profile(user_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM profile WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def save_goals(user_id, goals):
    conn = get_conn()
    conn.execute("DELETE FROM goals WHERE user_id=?", (user_id,))
    conn.executemany(
        "INSERT INTO goals (user_id, name, target_amount, deadline, priority) VALUES (?,?,?,?,?)",
        [(user_id, g["name"], g["target_amount"], g["deadline"], g["priority"]) for g in goals],
    )
    conn.commit()
    conn.close()


def get_goals(user_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM goals WHERE user_id=? ORDER BY priority", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_categories(user_id, cats):
    conn = get_conn()
    conn.execute("DELETE FROM budget_categories WHERE user_id=?", (user_id,))
    conn.executemany(
        "INSERT INTO budget_categories (user_id, name, monthly_limit, icon) VALUES (?,?,?,?)",
        [(user_id, c["name"], c["monthly_limit"], c["icon"]) for c in cats],
    )
    conn.commit()
    conn.close()


def get_categories(user_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM budget_categories WHERE user_id=?", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_expense(user_id, category_id, amount, note="", flagged=False, receipt_text=""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO expenses (user_id, category_id, amount, note, date, flagged, receipt_text) VALUES (?,?,?,?,?,?,?)",
        (user_id, category_id, amount, note, datetime.now().isoformat(), int(flagged), receipt_text),
    )
    conn.commit()
    conn.close()


def get_expenses_this_month(user_id):
    conn = get_conn()
    month = datetime.now().strftime("%Y-%m")
    rows = conn.execute(
        """SELECT e.*, b.name as category_name, b.monthly_limit, b.icon
           FROM expenses e
           JOIN budget_categories b ON e.category_id=b.id
           WHERE e.user_id=? AND e.date LIKE ?
           ORDER BY e.date DESC""",
        (user_id, f"{month}%"),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_spending_by_category(user_id):
    conn = get_conn()
    month = datetime.now().strftime("%Y-%m")
    rows = conn.execute(
        """SELECT b.id, b.name, b.monthly_limit, b.icon,
                  COALESCE(SUM(e.amount), 0) as spent
           FROM budget_categories b
           LEFT JOIN expenses e ON e.category_id=b.id AND e.user_id=? AND e.date LIKE ?
           WHERE b.user_id=?
           GROUP BY b.id""",
        (user_id, f"{month}%", user_id),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_expense(expense_id, user_id):
    conn = get_conn()
    conn.execute("DELETE FROM expenses WHERE id=? AND user_id=?", (expense_id, user_id))
    conn.commit()
    conn.close()


def create_alert(user_id, category_id, message):
    conn = get_conn()
    conn.execute(
        "INSERT INTO alerts (user_id, category_id, message, triggered_at) VALUES (?,?,?,?)",
        (user_id, category_id, message, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_active_alerts(user_id):
    conn = get_conn()
    rows = conn.execute(
        """SELECT a.*, b.name as category_name, b.icon
           FROM alerts a
           JOIN budget_categories b ON a.category_id=b.id
           WHERE a.user_id=? AND a.dismissed=0
           ORDER BY a.triggered_at DESC""",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def dismiss_alert(alert_id, user_id):
    conn = get_conn()
    conn.execute("UPDATE alerts SET dismissed=1 WHERE id=? AND user_id=?", (alert_id, user_id))
    conn.commit()
    conn.close()
