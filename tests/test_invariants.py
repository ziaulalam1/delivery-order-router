"""
Invariant tests for the delivery order router.

Invariant 1 — Every submitted order is assigned exactly once.
Invariant 2 — No dasher exceeds their declared capacity at any point.
Invariant 3 — When at least one dasher has capacity, assign_order must not raise.
Invariant 4 — When all dashers are at capacity, assign_order raises ValueError.
"""

import sys
import os
import uuid
import sqlite3
import pytest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Order
from router import init_db, get_db, seed_dashers, assign_order, get_all_assignments


def make_order(priority: int = 1) -> Order:
    return Order(
        order_id=str(uuid.uuid4()),
        restaurant_id="r-001",
        customer_id="c-001",
        items=["burger", "fries"],
        priority=priority,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def conn():
    c = get_db()
    init_db(c)
    yield c
    c.close()


@pytest.fixture
def seeded_conn(conn):
    seed_dashers(conn, [
        {"dasher_id": "d-001", "name": "Alex", "max_capacity": 3},
        {"dasher_id": "d-002", "name": "Jordan", "max_capacity": 3},
    ])
    return conn


# ---------------------------------------------------------------------------
# Invariant 1: every order assigned exactly once
# ---------------------------------------------------------------------------

def test_every_order_assigned_exactly_once(seeded_conn):
    orders = [make_order() for _ in range(6)]
    for o in orders:
        assign_order(seeded_conn, o)

    rows = seeded_conn.execute(
        "SELECT order_id, COUNT(*) AS cnt FROM assignments GROUP BY order_id HAVING cnt > 1"
    ).fetchall()
    assert rows == [], f"Duplicate assignment detected: {rows}"

    assigned_ids = {r["order_id"] for r in seeded_conn.execute("SELECT order_id FROM assignments").fetchall()}
    submitted_ids = {o.order_id for o in orders}
    assert submitted_ids == assigned_ids, "Not all orders were assigned"


# ---------------------------------------------------------------------------
# Invariant 2: no dasher exceeds max capacity
# ---------------------------------------------------------------------------

def test_no_dasher_exceeds_capacity(seeded_conn):
    # 2 dashers × 3 capacity = 6 max — fill all
    for _ in range(6):
        assign_order(seeded_conn, make_order())

    rows = seeded_conn.execute("""
        SELECT d.dasher_id, d.max_capacity, COUNT(aa.order_id) AS active
        FROM dashers d
        LEFT JOIN active_assignments aa ON d.dasher_id = aa.dasher_id
        GROUP BY d.dasher_id
    """).fetchall()

    for r in rows:
        assert r["active"] <= r["max_capacity"], (
            f"Dasher {r['dasher_id']} exceeded capacity: {r['active']} > {r['max_capacity']}"
        )


# ---------------------------------------------------------------------------
# Invariant 3: assignment succeeds when capacity available
# ---------------------------------------------------------------------------

def test_assignment_succeeds_when_capacity_available(seeded_conn):
    assignment = assign_order(seeded_conn, make_order())
    assert assignment.order_id is not None
    assert assignment.dasher_id is not None


# ---------------------------------------------------------------------------
# Invariant 4: ValueError raised when all dashers at capacity
# ---------------------------------------------------------------------------

def test_raises_when_all_dashers_at_capacity(seeded_conn):
    # Fill all slots: 2 dashers × 3 = 6 orders
    for _ in range(6):
        assign_order(seeded_conn, make_order())

    with pytest.raises(ValueError, match="no_capacity"):
        assign_order(seeded_conn, make_order())


# ---------------------------------------------------------------------------
# Invariant 5: load is distributed (greedy picks least-loaded dasher first)
# ---------------------------------------------------------------------------

def test_greedy_distributes_load(seeded_conn):
    for _ in range(4):
        assign_order(seeded_conn, make_order())

    rows = seeded_conn.execute("""
        SELECT dasher_id, COUNT(*) as cnt
        FROM active_assignments
        GROUP BY dasher_id
        ORDER BY cnt DESC
    """).fetchall()

    counts = [r["cnt"] for r in rows]
    # With 4 orders and 2 dashers of equal capacity, max difference should be 1
    assert max(counts) - min(counts) <= 1, f"Load imbalance detected: {counts}"


# ---------------------------------------------------------------------------
# Invariant 6: single-dasher setup respects capacity exactly
# ---------------------------------------------------------------------------

def test_single_dasher_exact_capacity():
    conn = get_db()
    init_db(conn)
    seed_dashers(conn, [{"dasher_id": "d-solo", "name": "Solo", "max_capacity": 2}])

    assign_order(conn, make_order())
    assign_order(conn, make_order())

    with pytest.raises(ValueError, match="no_capacity"):
        assign_order(conn, make_order())

    conn.close()
