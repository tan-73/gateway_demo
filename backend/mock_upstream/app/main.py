import asyncio
import random
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, FastAPI, HTTPException, Response
from pydantic import BaseModel

PRODUCTS = [
    {"id": "sku-1", "name": "Starter Sneakers", "price": 59.0, "category": "footwear"},
    {"id": "sku-2", "name": "Canvas Daypack", "price": 79.0, "category": "bags"},
    {"id": "sku-3", "name": "Trail Bottle", "price": 24.0, "category": "outdoors"},
]

INVENTORY = {
    "sku-1": {"product_id": "sku-1", "available": 14, "warehouse": "blr-1"},
    "sku-2": {"product_id": "sku-2", "available": 6, "warehouse": "bom-2"},
    "sku-3": {"product_id": "sku-3", "available": 21, "warehouse": "del-1"},
}

REVIEWS = {
    "sku-1": [
        {"author": "Ava", "rating": 5, "headline": "Great everyday pair"},
        {"author": "Noah", "rating": 4, "headline": "Comfortable and light"},
    ],
    "sku-2": [
        {"author": "Ivy", "rating": 4, "headline": "Ideal commuter bag"},
    ],
    "sku-3": [
        {"author": "Mila", "rating": 5, "headline": "Keeps water cold for hours"},
    ],
}


class RecommendationRequest(BaseModel):
    customer_id: str
    cart: list[str]
    context: Optional[str] = None


public_router = APIRouter(prefix="/public")
standard_router = APIRouter(prefix="/standard")
premium_router = APIRouter(prefix="/premium")


@public_router.get("/products")
async def list_products():
    return {"storefront": "catalog", "items": PRODUCTS, "count": len(PRODUCTS), "timestamp": datetime.utcnow().isoformat()}


@public_router.get("/products/{product_id}")
async def get_product(product_id: str):
    product = next((item for item in PRODUCTS if item["id"] == product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"storefront": "catalog", "item": product, "timestamp": datetime.utcnow().isoformat()}


@standard_router.get("/inventory/{product_id}")
async def get_inventory(product_id: str):
    inventory = INVENTORY.get(product_id)
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory record not found")
    return {"storefront": "inventory", "item": inventory, "timestamp": datetime.utcnow().isoformat()}


@standard_router.get("/reviews/{product_id}")
async def get_reviews(product_id: str):
    reviews = REVIEWS.get(product_id)
    if reviews is None:
        raise HTTPException(status_code=404, detail="Reviews not found")
    return {"storefront": "reviews", "product_id": product_id, "items": reviews, "timestamp": datetime.utcnow().isoformat()}


@premium_router.post("/recommendations")
async def get_recommendations(payload: RecommendationRequest):
    await asyncio.sleep(random.uniform(0.3, 0.8))
    suggestions = [
        {"product_id": "sku-2", "reason": "Often bought with day-to-day footwear"},
        {"product_id": "sku-3", "reason": "Pairs well with active lifestyle items"},
    ]
    return {
        "storefront": "recommendations",
        "customer_id": payload.customer_id,
        "cart": payload.cart,
        "suggestions": suggestions,
        "timestamp": datetime.utcnow().isoformat(),
    }


@premium_router.get("/analytics/customer-segment/{segment_id}")
async def get_segment(segment_id: str):
    await asyncio.sleep(random.uniform(0.3, 0.8))
    return {
        "storefront": "analytics",
        "segment_id": segment_id,
        "avg_order_value": 132.4,
        "top_categories": ["footwear", "bags", "outdoors"],
        "conversion_rate": 0.183,
        "timestamp": datetime.utcnow().isoformat(),
    }


@premium_router.get("/analytics/fail")
async def fail():
    await asyncio.sleep(random.uniform(0.3, 0.5))
    return Response(content='{"detail":"analytics upstream failure"}', status_code=500, media_type="application/json")


app = FastAPI(title="Mock Upstream")
app.include_router(public_router)
app.include_router(standard_router)
app.include_router(premium_router)
