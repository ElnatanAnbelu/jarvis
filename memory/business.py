"""
Business OS database layer — SQLite-backed registry for Nexel businesses.
Tables: businesses, kpis, contacts, interactions, financials, goals, team
"""
import sqlite3
import json
from datetime import datetime, date
from pathlib import Path

DB_PATH = Path(__file__).parent / "business.db"


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with _conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS businesses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT UNIQUE NOT NULL,
            type        TEXT,
            stage       TEXT DEFAULT 'idea',
            description TEXT,
            revenue_model TEXT,
            mrr         REAL DEFAULT 0,
            arr         REAL DEFAULT 0,
            founded     TEXT,
            active      INTEGER DEFAULT 1,
            created_at  TEXT DEFAULT (datetime('now')),
            updated_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS business_team (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            name        TEXT NOT NULL,
            role        TEXT,
            FOREIGN KEY(business_id) REFERENCES businesses(id)
        );

        CREATE TABLE IF NOT EXISTS kpis (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            name        TEXT NOT NULL,
            current     REAL DEFAULT 0,
            target      REAL,
            unit        TEXT,
            period      TEXT DEFAULT 'monthly',
            updated_at  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(business_id) REFERENCES businesses(id)
        );

        CREATE TABLE IF NOT EXISTS contacts (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id    INTEGER,
            name           TEXT NOT NULL,
            role           TEXT,
            company        TEXT,
            email          TEXT,
            phone          TEXT,
            notes          TEXT,
            pipeline_stage TEXT DEFAULT 'lead',
            last_contact   TEXT,
            follow_up_date TEXT,
            created_at     TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(business_id) REFERENCES businesses(id)
        );

        CREATE TABLE IF NOT EXISTS interactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_id  INTEGER,
            business_id INTEGER,
            type        TEXT,
            notes       TEXT,
            date        TEXT,
            created_at  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(contact_id) REFERENCES contacts(id)
        );

        CREATE TABLE IF NOT EXISTS financials (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            type        TEXT NOT NULL,
            amount      REAL NOT NULL,
            category    TEXT,
            date        TEXT,
            notes       TEXT,
            created_at  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(business_id) REFERENCES businesses(id)
        );

        CREATE TABLE IF NOT EXISTS business_goals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            title       TEXT NOT NULL,
            description TEXT,
            target_date TEXT,
            status      TEXT DEFAULT 'active',
            created_at  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(business_id) REFERENCES businesses(id)
        );
        """)


init_db()


# ── HELPERS ──────────────────────────────────────────────────────────────────

def _now():
    return datetime.now().isoformat(timespec="seconds")


def _get_business_id(name: str):
    with _conn() as conn:
        row = conn.execute(
            "SELECT id FROM businesses WHERE lower(name)=lower(?)", (name,)
        ).fetchone()
    return row["id"] if row else None


def _require_business(name: str) -> int:
    bid = _get_business_id(name)
    if bid is None:
        raise ValueError(f"Business '{name}' not found. Add it first with add_business.")
    return bid


# ── BUSINESS REGISTRY ─────────────────────────────────────────────────────────

def add_business(name: str, type: str = "", stage: str = "idea",
                 description: str = "", revenue_model: str = "",
                 founded: str = "", mrr: float = 0) -> dict:
    with _conn() as conn:
        conn.execute(
            """INSERT INTO businesses (name,type,stage,description,revenue_model,founded,mrr,arr,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (name, type, stage, description, revenue_model, founded, mrr, mrr * 12, _now())
        )
    return get_business(name)


def update_business(name: str, **fields) -> dict:
    bid = _require_business(name)
    allowed = {"type", "stage", "description", "revenue_model", "mrr", "arr", "founded", "active"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if "mrr" in updates and "arr" not in updates:
        updates["arr"] = updates["mrr"] * 12
    if not updates:
        raise ValueError(f"No valid fields to update. Allowed: {allowed}")
    updates["updated_at"] = _now()
    set_clause = ", ".join(f"{k}=?" for k in updates)
    with _conn() as conn:
        conn.execute(f"UPDATE businesses SET {set_clause} WHERE id=?",
                     list(updates.values()) + [bid])
    return get_business(name)


def get_business(name: str) -> dict:
    bid = _require_business(name)
    with _conn() as conn:
        b = dict(conn.execute("SELECT * FROM businesses WHERE id=?", (bid,)).fetchone())
        b["team"] = [dict(r) for r in conn.execute(
            "SELECT name, role FROM business_team WHERE business_id=?", (bid,)).fetchall()]
        b["goals"] = [dict(r) for r in conn.execute(
            "SELECT title, status, target_date FROM business_goals WHERE business_id=? AND status='active'", (bid,)).fetchall()]
        b["kpis"] = [dict(r) for r in conn.execute(
            "SELECT name, current, target, unit, period FROM kpis WHERE business_id=?", (bid,)).fetchall()]
    return b


def list_businesses() -> list:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, name, type, stage, mrr, active FROM businesses ORDER BY created_at"
        ).fetchall()
    return [dict(r) for r in rows]


def add_team_member(business: str, name: str, role: str = "") -> str:
    bid = _require_business(business)
    with _conn() as conn:
        conn.execute("INSERT INTO business_team (business_id, name, role) VALUES (?,?,?)",
                     (bid, name, role))
    return f"{name} added to {business} team as {role or 'team member'}."


def add_business_goal(business: str, title: str, description: str = "", target_date: str = "") -> str:
    bid = _require_business(business)
    with _conn() as conn:
        conn.execute(
            "INSERT INTO business_goals (business_id, title, description, target_date) VALUES (?,?,?,?)",
            (bid, title, description, target_date)
        )
    return f"Goal added to {business}: '{title}'"


def complete_goal(business: str, title: str) -> str:
    bid = _require_business(business)
    with _conn() as conn:
        conn.execute(
            "UPDATE business_goals SET status='done' WHERE business_id=? AND lower(title) LIKE lower(?)",
            (bid, f"%{title}%")
        )
    return f"Goal marked complete: '{title}'"


# ── KPI TRACKING ──────────────────────────────────────────────────────────────

def set_kpi(business: str, kpi_name: str, target: float, unit: str = "",
            period: str = "monthly", current: float = 0) -> str:
    bid = _require_business(business)
    with _conn() as conn:
        existing = conn.execute(
            "SELECT id FROM kpis WHERE business_id=? AND lower(name)=lower(?)", (bid, kpi_name)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE kpis SET target=?, unit=?, period=?, current=?, updated_at=? WHERE id=?",
                (target, unit, period, current, _now(), existing["id"])
            )
        else:
            conn.execute(
                "INSERT INTO kpis (business_id, name, current, target, unit, period, updated_at) VALUES (?,?,?,?,?,?,?)",
                (bid, kpi_name, current, target, unit, period, _now())
            )
    return f"KPI '{kpi_name}' set for {business}: target {target} {unit} ({period})"


def update_kpi(business: str, kpi_name: str, current: float) -> str:
    bid = _require_business(business)
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, target, unit FROM kpis WHERE business_id=? AND lower(name)=lower(?)",
            (bid, kpi_name)
        ).fetchone()
        if not row:
            return f"KPI '{kpi_name}' not found for {business}. Set it first with set_kpi."
        conn.execute("UPDATE kpis SET current=?, updated_at=? WHERE id=?",
                     (current, _now(), row["id"]))
        pct = (current / row["target"] * 100) if row["target"] else 0
        unit = row["unit"] or ""
    return f"{business} / {kpi_name}: {current} {unit} ({pct:.1f}% of target)"


def get_kpis(business: str) -> list:
    bid = _require_business(business)
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM kpis WHERE business_id=?", (bid,)).fetchall()
    return [dict(r) for r in rows]


# ── CRM ───────────────────────────────────────────────────────────────────────

def add_contact(business: str, name: str, role: str = "", company: str = "",
                email: str = "", phone: str = "", notes: str = "",
                pipeline_stage: str = "lead") -> str:
    bid = _get_business_id(business) if business else None
    with _conn() as conn:
        conn.execute(
            """INSERT INTO contacts (business_id,name,role,company,email,phone,notes,pipeline_stage,created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (bid, name, role, company, email, phone, notes, pipeline_stage, _now())
        )
    return f"Contact '{name}' ({role}) added{' to ' + business if business else ''}."


def log_interaction(contact_name: str, interaction_type: str, notes: str,
                    business: str = "", date_str: str = "") -> str:
    with _conn() as conn:
        c_row = conn.execute(
            "SELECT id, business_id FROM contacts WHERE lower(name) LIKE lower(?)",
            (f"%{contact_name}%",)
        ).fetchone()
        if not c_row:
            return f"Contact '{contact_name}' not found. Add them first with add_contact."
        cid = c_row["id"]
        bid = _get_business_id(business) if business else c_row["business_id"]
        log_date = date_str or _now()[:10]
        conn.execute(
            "INSERT INTO interactions (contact_id, business_id, type, notes, date) VALUES (?,?,?,?,?)",
            (cid, bid, interaction_type, notes, log_date)
        )
        conn.execute(
            "UPDATE contacts SET last_contact=?, updated_at=? WHERE id=?",
            (log_date, _now(), cid)
        ) if False else None
        conn.execute("UPDATE contacts SET last_contact=? WHERE id=?", (log_date, cid))
    return f"Logged {interaction_type} with {contact_name}: {notes[:80]}"


def update_contact_stage(contact_name: str, stage: str) -> str:
    valid = {"lead", "contacted", "negotiating", "closed", "churned"}
    if stage not in valid:
        return f"Invalid stage '{stage}'. Valid: {', '.join(sorted(valid))}"
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, name FROM contacts WHERE lower(name) LIKE lower(?)", (f"%{contact_name}%",)
        ).fetchone()
        if not row:
            return f"Contact '{contact_name}' not found."
        conn.execute("UPDATE contacts SET pipeline_stage=? WHERE id=?", (stage, row["id"]))
        return f"{row['name']} moved to '{stage}'."


def set_follow_up(contact_name: str, follow_up_date: str) -> str:
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, name FROM contacts WHERE lower(name) LIKE lower(?)", (f"%{contact_name}%",)
        ).fetchone()
        if not row:
            return f"Contact '{contact_name}' not found."
        conn.execute("UPDATE contacts SET follow_up_date=? WHERE id=?", (follow_up_date, row["id"]))
        return f"Follow-up with {row['name']} set for {follow_up_date}."


def get_pipeline(business: str = "") -> list:
    with _conn() as conn:
        if business:
            bid = _get_business_id(business)
            rows = conn.execute(
                "SELECT name, role, company, pipeline_stage, last_contact, follow_up_date FROM contacts WHERE business_id=? ORDER BY pipeline_stage, name",
                (bid,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT name, role, company, pipeline_stage, last_contact, follow_up_date FROM contacts ORDER BY pipeline_stage, name"
            ).fetchall()
    return [dict(r) for r in rows]


def get_follow_ups_due(days_since: int = 14) -> list:
    """Return contacts not touched in N days, or with follow_up_date <= today."""
    today = date.today().isoformat()
    with _conn() as conn:
        rows = conn.execute(f"""
            SELECT name, role, company, pipeline_stage, last_contact, follow_up_date,
                   julianday('now') - julianday(last_contact) as days_since_contact
            FROM contacts
            WHERE (follow_up_date IS NOT NULL AND follow_up_date <= ?)
               OR (last_contact IS NOT NULL AND julianday('now') - julianday(last_contact) >= ?)
               OR (last_contact IS NULL)
            ORDER BY days_since_contact DESC
        """, (today, days_since)).fetchall()
    return [dict(r) for r in rows]


def get_interactions(contact_name: str, limit: int = 10) -> list:
    with _conn() as conn:
        c_row = conn.execute(
            "SELECT id FROM contacts WHERE lower(name) LIKE lower(?)", (f"%{contact_name}%",)
        ).fetchone()
        if not c_row:
            return []
        rows = conn.execute(
            "SELECT type, notes, date FROM interactions WHERE contact_id=? ORDER BY date DESC LIMIT ?",
            (c_row["id"], limit)
        ).fetchall()
    return [dict(r) for r in rows]


# ── FINANCIALS ────────────────────────────────────────────────────────────────

def log_financial(business: str, type: str, amount: float, category: str = "",
                  date_str: str = "", notes: str = "") -> str:
    bid = _require_business(business)
    entry_date = date_str or date.today().isoformat()
    with _conn() as conn:
        conn.execute(
            "INSERT INTO financials (business_id, type, amount, category, date, notes) VALUES (?,?,?,?,?,?)",
            (bid, type, amount, category, entry_date, notes)
        )
    label = "Revenue" if type == "revenue" else "Expense"
    return f"{label} logged for {business}: ${amount:,.2f} ({category}) on {entry_date}"


def get_financials(business: str, period: str = "all") -> dict:
    bid = _require_business(business)
    with _conn() as conn:
        if period == "month":
            where = "AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')"
        elif period == "year":
            where = "AND strftime('%Y', date) = strftime('%Y', 'now')"
        else:
            where = ""
        rows = conn.execute(
            f"SELECT type, amount, category, date, notes FROM financials WHERE business_id=? {where} ORDER BY date DESC",
            (bid,)
        ).fetchall()
    revenue = sum(r["amount"] for r in rows if r["type"] == "revenue")
    expenses = sum(r["amount"] for r in rows if r["type"] == "expense")
    return {
        "business": business,
        "period": period,
        "revenue": revenue,
        "expenses": expenses,
        "profit": revenue - expenses,
        "margin": ((revenue - expenses) / revenue * 100) if revenue else 0,
        "transactions": [dict(r) for r in rows],
    }


def get_nexel_financials() -> dict:
    """Aggregate P&L across all active businesses."""
    businesses = list_businesses()
    summary = []
    total_revenue = 0
    total_expenses = 0
    for b in businesses:
        if not b["active"]:
            continue
        bid = b["id"]
        with _conn() as conn:
            rev = conn.execute(
                "SELECT COALESCE(SUM(amount),0) FROM financials WHERE business_id=? AND type='revenue'", (bid,)
            ).fetchone()[0]
            exp = conn.execute(
                "SELECT COALESCE(SUM(amount),0) FROM financials WHERE business_id=? AND type='expense'", (bid,)
            ).fetchone()[0]
        total_revenue += rev
        total_expenses += exp
        summary.append({
            "business": b["name"],
            "revenue": rev,
            "expenses": exp,
            "profit": rev - exp,
        })
    return {
        "businesses": summary,
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "total_profit": total_revenue - total_expenses,
    }


def cash_flow_projection(business: str) -> dict:
    """Estimate runway based on monthly burn and revenue."""
    bid = _require_business(business)
    with _conn() as conn:
        monthly = conn.execute("""
            SELECT type, COALESCE(AVG(monthly_total),0) as avg
            FROM (
                SELECT type, strftime('%Y-%m', date) as month, SUM(amount) as monthly_total
                FROM financials WHERE business_id=?
                GROUP BY type, month
            )
            GROUP BY type
        """, (bid,)).fetchall()
    avg_rev = next((r["avg"] for r in monthly if r["type"] == "revenue"), 0)
    avg_exp = next((r["avg"] for r in monthly if r["type"] == "expense"), 0)
    net_monthly = avg_rev - avg_exp
    b_row = get_business(business)
    mrr = b_row.get("mrr", 0) or avg_rev
    runway_months = None
    if net_monthly < 0:
        runway_months = None  # would need cash balance to calc properly
    return {
        "business": business,
        "avg_monthly_revenue": avg_rev,
        "avg_monthly_expenses": avg_exp,
        "avg_monthly_burn": avg_exp,
        "net_monthly": net_monthly,
        "mrr": mrr,
        "status": "profitable" if net_monthly >= 0 else "burning",
    }
