# API Gateway Demonstration System

API gateway demo built with FastAPI, SQLite, in-process rate limiting/cache state, APScheduler, and a React/Vite/Tailwind dashboard. Runs locally or hosted (Render + Vercel/Render static site).

The demo uses a concrete storefront use case instead of generic echo APIs:

- public catalog APIs for products
- standard APIs for inventory and reviews
- premium APIs for recommendations and customer-segment analytics

## Live Demo

**URL:** https://gateway-demo-2.onrender.com/

> The backend runs on Render's free tier, which sleeps after ~15 minutes of inactivity. If the very first request feels slow (~30-50s), that's a cold start warming back up — refresh and it'll be fast from then on.

### How to test

1. Open the URL above.
2. Log in as admin: `admin@gateway-demo.local` / `demo-admin-pass`.
3. In the API Keys form, pick a user (e.g. `developer@demo.local`) and a plan (e.g. `Pro`), then click **Create API Key**.
4. Copy the raw key shown once in the green banner.
5. Click **Log Out**.
6. Click the **Consumer API Key** tab, paste the key, click **Exchange API Key**.
7. Catalog Preview should show 3 products (public tier).
8. In Gateway Explorer, enter a product id (`sku-1`, `sku-2`, or `sku-3`) and click **Fetch** — Product / Inventory / Reviews should populate (standard tier).
9. Click **Run Premium Call** — suggestions should appear and the Credits counter should drop (premium tier).
10. Click **Fetch** or **Run Premium Call** repeatedly — you'll eventually see a rate-limit error banner instead of a result; it clears on the next successful call.
11. Log back in as admin and click **Run Renewal** to see a `scheduled_renewal` entry appear in the Credit Ledger.

## Structure

- `backend/core_app`: core FastAPI app for auth, gateway, admin API, scheduler, persistence, and tests
- `backend/mock_upstream`: single mock upstream FastAPI app exposing public/standard/premium storefront APIs under prefixed routes
- `dashboard`: React/Vite/Tailwind SPA

## Local Development Setup

1. Create a Python virtual environment and install backend dependencies:
   - `pip install -r backend/core_app/requirements.txt`
2. Install dashboard dependencies:
   - `npm install --prefix dashboard`
3. Start the mock upstream:
   - `python -m uvicorn app.main:app --app-dir backend/mock_upstream --host 127.0.0.1 --port 8101 --reload`
4. Start the core API:
   - `python -m uvicorn app.main:app --app-dir backend/core_app --host 127.0.0.1 --port 8000 --reload`
5. Start the dashboard:
   - `npm run dev --prefix dashboard`

## Demo flow

- Log in to the admin console:
  - `POST http://127.0.0.1:8000/auth/admin-login`
  - default demo credentials:
    - `admin@gateway-demo.local`
    - `demo-admin-pass`
- Create a consumer API key from the admin UI or `POST /admin/api-keys`
- Exchange the consumer API key:
  - `curl -X POST http://127.0.0.1:8000/auth/token -H "Content-Type: application/json" -d "{\"api_key\":\"<raw-key>\"}"`
- Browse the storefront catalog through the gateway:
  - `GET http://127.0.0.1:8000/api/catalog/products` with `Authorization: Bearer <jwt>`
- Fetch a product detail through the gateway:
  - `GET http://127.0.0.1:8000/api/catalog/products/sku-1`
- Fetch standard inventory and reviews:
  - `GET http://127.0.0.1:8000/api/inventory/sku-1`
  - `GET http://127.0.0.1:8000/api/reviews/sku-1`
- Trigger a premium recommendation request:
  - `POST http://127.0.0.1:8000/api/recommendations`
- Trigger a dynamic config change:
  - `PATCH /admin/routes/{id}` or `PATCH /admin/plans/{id}`
- Trigger renewal:
  - `POST /admin/jobs/run-renewal`

## Testing

- Run: `pytest backend/core_app/tests -q`

## Notes

- JWT is used for identity only; each request reloads live key/plan state before rate-limit, validity, and billing checks.
- All mutating admin operations write audit log entries.
- In-memory rate-limit and cache state assume a single worker per process for this demo.
- The public/standard/premium route categories now map to realistic storefront APIs rather than generic echo services.
- Hosted demos should use `POST /auth/admin-login` for admin access; one-time seeded API keys are no longer required to bootstrap the dashboard.
