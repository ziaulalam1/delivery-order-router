from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Order(BaseModel):
    order_id: str
    restaurant_id: str
    customer_id: str
    items: list[str]
    priority: int = Field(default=1, ge=1, le=5)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Dasher(BaseModel):
    dasher_id: str
    name: str
    current_capacity: int = Field(default=3, ge=1, le=10)
    active_orders: list[str] = Field(default_factory=list)
    available: bool = True

    @property
    def has_capacity(self) -> bool:
        return self.available and len(self.active_orders) < self.current_capacity


class Assignment(BaseModel):
    assignment_id: str
    order_id: str
    dasher_id: str
    assigned_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "assigned"


class OrderRequest(BaseModel):
    restaurant_id: str
    customer_id: str
    items: list[str]
    priority: int = Field(default=1, ge=1, le=5)


class AssignmentResponse(BaseModel):
    assignment_id: str
    order_id: str
    dasher_id: str
    dasher_name: str
    status: str
    assigned_at: str
