import asyncio
import random
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Response
from pydantic import BaseModel


class RecommendationRequest(BaseModel):
    customer_id: str
    cart: list[str]
    context: Optional[str] = None

app = FastAPI(title="Mock Upstream Premium")


@app.post("/recommendations")
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


@app.get("/analytics/customer-segment/{segment_id}")
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


@app.get("/analytics/fail")
async def fail():
    await asyncio.sleep(random.uniform(0.3, 0.5))
    return Response(content='{"detail":"analytics upstream failure"}', status_code=500, media_type="application/json")
