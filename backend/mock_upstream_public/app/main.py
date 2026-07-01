from datetime import datetime

from fastapi import FastAPI, HTTPException

PRODUCTS = [
    {"id": "sku-1", "name": "Starter Sneakers", "price": 59.0, "category": "footwear"},
    {"id": "sku-2", "name": "Canvas Daypack", "price": 79.0, "category": "bags"},
    {"id": "sku-3", "name": "Trail Bottle", "price": 24.0, "category": "outdoors"},
]

app = FastAPI(title="Mock Upstream Public")


@app.get("/products")
async def list_products():
    return {"storefront": "catalog", "items": PRODUCTS, "count": len(PRODUCTS), "timestamp": datetime.utcnow().isoformat()}


@app.get("/products/{product_id}")
async def get_product(product_id: str):
    product = next((item for item in PRODUCTS if item["id"] == product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"storefront": "catalog", "item": product, "timestamp": datetime.utcnow().isoformat()}
