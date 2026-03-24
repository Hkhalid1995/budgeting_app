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
            id INTEGER PRIMARY KEY,
            name TEXT,
            monthly_income REAL,
            currency TEXT DEFAULT 'PKR',
            created_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            target_amount REAL,
            deadline TEXT,
            priority INTEGER DEFAULT 1
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS budget_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            monthly_limit REAL,
            icon TEXT DEFAULT '📁'
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            amount REAL,
            note TEXT,
            date TEXT,
            flagged INTEGER DEFAULT 0,
            FOREIGN KEY (category_id) REFERENCES budget_categories(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            message TEXT,
            triggered_at TEXT,
            dismissed INTEGER DEFAULT 0,
            FOREIGN KEY (category_id) REFERENCES budget_categories(id)
        )
    """)

    conn.commit()
    conn.close()


# ── Profile ────────────────────────────────────────────────
def save_profile(name, monthly_income, currency="PKR"):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM profile")
    c.execute(
        "INSERT INTO profile (name, monthly_income, currency, created_at) VALUES (?,?,?,?)",
        (name, monthly_income, currency, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_profile():
    conn = get_conn()
    row = conn.execute("SELECT * FROM profile LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None


# ── Goals ──────────────────────────────────────────────────
def save_goals(goals: list[dict]):
    conn = get_conn()
    conn.execute("DELETE FROM goals")
    conn.executemany(
        "INSERT INTO goals (name, target_amount, deadline, priority) VALUES (?,?,?,?)",
        [(g["name"], g["target_amount"], g["deadline"], g["priority"]) for g in goals],
    )
    conn.commit()
    conn.close()


def get_goals():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM goals ORDER BY priority").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Budget categories ──────────────────────────────────────
def save_categories(cats: list[dict]):
    conn = get_conn()
    conn.execute("DELETE FROM budget_categories")
    conn.executemany(
        "INSERT INTO budget_categories (name, monthly_limit, icon) VALUES (?,?,?)",
        [(c["name"], c["monthly_limit"], c["icon"]) for c in cats],
    )
    conn.commit()
    conn.close()


def get_categories():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM budget_categories").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Expenses ───────────────────────────────────────────────
def add_expense(category_id, amount, note="", flagged=False):
    conn = get_conn()
    conn.execute(
        "INSERT INTO expenses (category_id, amount, note, date, flagged) VALUES (?,?,?,?,?)",
        (category_id, amount, note, datetime.now().isoformat(), int(flagged)),
    )
    conn.commit()
    conn.close()


def get_expenses_this_month():
    conn = get_conn()
    month = datetime.now().strftime("%Y-%m")
    rows = conn.execute(
        """
        SELECT e.*, b.name as category_name, b.monthly_limit, b.icon
        FROM expenses e
        JOIN budget_categories b ON e.category_id = b.id
        WHERE e.date LIKE ?
        ORDER BY e.date DESC
        """,
        (f"{month}%",),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_spending_by_category():
    conn = get_conn()
    month = datetime.now().strftime("%Y-%m")
    rows = conn.execute(
        """
        SELECT b.id, b.name, b.monthly_limit, b.icon,
               COALESCE(SUM(e.amount), 0) as spent
        FROM budget_categories b
        LEFT JOIN expenses e ON e.category_id = b.id AND e.date LIKE ?
        GROUP BY b.id
        """,
        (f"{month}%",),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Alerts ─────────────────────────────────────────────────
def create_alert(category_id, message):
    conn = get_conn()
    conn.execute(
        "INSERT INTO alerts (category_id, message, triggered_at) VALUES (?,?,?)",
        (category_id, message, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_active_alerts():
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT a.*, b.name as category_name, b.icon
        FROM alerts a
        JOIN budget_categories b ON a.category_id = b.id
        WHERE a.dismissed = 0
        ORDER BY a.triggered_at DESC
        """,
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def dismiss_alert(alert_id):
    conn = get_conn()
    conn.execute("UPDATE alerts SET dismissed=1 WHERE id=?", (alert_id,))
    conn.commit()
    conn.close()
