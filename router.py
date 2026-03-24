"""
Greedy assignment router: assign each incoming order to the first available
dasher with remaining capacity, ordered by fewest active orders (load balance).
Invariants enforced:
  - Every submitted order is assigned exactly once.
  - No dasher exceeds their declared capacity.
"""

import sqlite3
import uuid
from datetime import datetime
from typing import Optional
from models import Order, Dasher, Assignment


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# Module-level in-memory DB (shared within a single process)
_db: Optional[sqlite3.Connection] = None


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            restaurant_id TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            items TEXT NOT NULL,
            priority INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS dashers (
            dasher_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            max_capacity INTEGER NOT NULL DEFAULT 3,
            available INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS active_assignments (
            dasher_id TEXT NOT NULL,
            order_id TEXT NOT NULL,
            PRIMARY KEY (dasher_id, order_id),
            FOREIGN KEY (dasher_id) REFERENCES dashers(dasher_id),
            FOREIGN KEY (order_id) REFERENCES orders(order_id)
        );

        CREATE TABLE IF NOT EXISTS assignments (
            assignment_id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL UNIQUE,
            dasher_id TEXT NOT NULL,
            assigned_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'assigned'
        );
    """)
    conn.commit()


def seed_dashers(conn: sqlite3.Connection, dashers: list[dict]) -> None:
    conn.executemany(
        "INSERT OR IGNORE INTO dashers (dasher_id, name, max_capacity, available) VALUES (?, ?, ?, ?)",
        [(d["dasher_id"], d["name"], d.get("max_capacity", 3), 1) for d in dashers],
    )
    conn.commit()


def assign_order(conn: sqlite3.Connection, order: Order) -> Assignment:
    """
    Greedy assignment: pick dasher with lowest load that still has capacity.
    Raises ValueError if no dasher has capacity.
    All steps run inside a single transaction to prevent double-assignment.
    """
    with conn:
        # Insert order (idempotent via PRIMARY KEY constraint)
        conn.execute(
            "INSERT INTO orders (order_id, restaurant_id, customer_id, items, priority, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                order.order_id,
                order.restaurant_id,
                order.customer_id,
                ",".join(order.items),
                order.priority,
                order.created_at.isoformat(),
            ),
        )

        # Find best dasher: available, under capacity, fewest active orders first
        row = conn.execute("""
            SELECT d.dasher_id, d.name, d.max_capacity,
                   COUNT(aa.order_id) AS active_count
            FROM dashers d
            LEFT JOIN active_assignments aa ON d.dasher_id = aa.dasher_id
            WHERE d.available = 1
            GROUP BY d.dasher_id
            HAVING active_count < d.max_capacity
            ORDER BY active_count ASC, d.dasher_id ASC
            LIMIT 1
        """).fetchone()

        if row is None:
            raise ValueError("no_capacity: all dashers at max load")

        dasher_id = row["dasher_id"]
        assignment_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        conn.execute(
            "INSERT INTO assignments (assignment_id, order_id, dasher_id, assigned_at, status) VALUES (?, ?, ?, ?, ?)",
            (assignment_id, order.order_id, dasher_id, now, "assigned"),
        )
        conn.execute(
            "INSERT INTO active_assignments (dasher_id, order_id) VALUES (?, ?)",
            (dasher_id, order.order_id),
        )

    return Assignment(
        assignment_id=assignment_id,
        order_id=order.order_id,
        dasher_id=dasher_id,
        assigned_at=datetime.fromisoformat(now),
    )


def get_all_assignments(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("""
        SELECT a.assignment_id, a.order_id, a.dasher_id, d.name AS dasher_name,
               a.assigned_at, a.status
        FROM assignments a
        JOIN dashers d ON a.dasher_id = d.dasher_id
        ORDER BY a.assigned_at
    """).fetchall()
    return [dict(r) for r in rows]
