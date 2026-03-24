"""
Delivery Order Router — FastAPI service
POST /orders   → submit an order, get back an assignment
GET  /assignments → list all assignments
"""

import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException
from models import OrderRequest, AssignmentResponse, Order
from router import init_db, get_db, seed_dashers, assign_order, get_all_assignments

_conn = None

DEFAULT_DASHERS = [
    {"dasher_id": f"d-{i:04d}", "name": f"Dasher {i:04d}", "max_capacity": 3}
    for i in range(1, 401)  # 400 dashers × 3 capacity = 1,200 total slots
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _conn
    _conn = get_db()
    init_db(_conn)
    seed_dashers(_conn, DEFAULT_DASHERS)
    yield
    _conn.close()


app = FastAPI(title="Delivery Order Router", lifespan=lifespan)


@app.post("/orders", response_model=AssignmentResponse, status_code=201)
def submit_order(req: OrderRequest):
    order = Order(
        order_id=str(uuid.uuid4()),
        restaurant_id=req.restaurant_id,
        customer_id=req.customer_id,
        items=req.items,
        priority=req.priority,
        created_at=datetime.utcnow(),
    )
    try:
        assignment = assign_order(_conn, order)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    dasher_row = _conn.execute(
        "SELECT name FROM dashers WHERE dasher_id = ?", (assignment.dasher_id,)
    ).fetchone()

    return AssignmentResponse(
        assignment_id=assignment.assignment_id,
        order_id=assignment.order_id,
        dasher_id=assignment.dasher_id,
        dasher_name=dasher_row["name"],
        status=assignment.status,
        assigned_at=assignment.assigned_at.isoformat(),
    )


@app.get("/assignments", response_model=list[AssignmentResponse])
def list_assignments():
    rows = get_all_assignments(_conn)
    return [
        AssignmentResponse(
            assignment_id=r["assignment_id"],
            order_id=r["order_id"],
            dasher_id=r["dasher_id"],
            dasher_name=r["dasher_name"],
            status=r["status"],
            assigned_at=r["assigned_at"],
        )
        for r in rows
    ]
