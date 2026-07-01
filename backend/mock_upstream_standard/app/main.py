from datetime import datetime

from fastapi import FastAPI, HTTPException

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

app = FastAPI(title="Mock Upstream Standard")


@app.get("/inventory/{product_id}")
async def get_inventory(product_id: str):
    inventory = INVENTORY.get(product_id)
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory record not found")
    return {"storefront": "inventory", "item": inventory, "timestamp": datetime.utcnow().isoformat()}


@app.get("/reviews/{product_id}")
async def get_reviews(product_id: str):
    reviews = REVIEWS.get(product_id)
    if reviews is None:
        raise HTTPException(status_code=404, detail="Reviews not found")
    return {"storefront": "reviews", "product_id": product_id, "items": reviews, "timestamp": datetime.utcnow().isoformat()}
