# Interview cheat sheet (personal notes, not part of the app)

## 60-second pitch

"MiniShop is a Django e-commerce app: catalog, session cart, checkout with Stripe, a DRF API with OpenAPI docs, and a staff sales dashboard. The interesting parts are correctness problems: never overselling stock under concurrency, handling payment webhooks that arrive late or twice, and keeping money exact. It's tested (70+ tests including a Postgres concurrency test), containerised, and has CI."

## 5-minute demo script

1. `docker compose up --build`, then `seed_demo`. Open http://localhost:8000.
2. Search and filter, add items to the cart (point out the navbar badge updating without a reload: HTMX).
3. Checkout as a guest, then pay on the mock page. Show the order marked **Paid**.
4. Log in as `admin`, open `/dashboard/`: revenue chart, top products, low stock.
5. Open `/api/docs/`, run `GET /api/products/`, then show `POST /api/orders/` (log in as admin first for Swagger, or use `curl -u admin:admin`). Product 3 has only 8 in stock, so quantity 9 returns a 409.
6. Open `orders/services.py` and walk through `create_order`: the lock, the rollback, the snapshot.
7. Run `uv run pytest` and mention the concurrency test.

## Questions you should expect, with answers

**How do you stop two people buying the last item?**
Inside one transaction, `create_order` locks the product rows with `select_for_update` and checks and decrements stock. The second buyer waits on the lock, then sees stock 0 and gets `OutOfStock`. Rows are locked in pk order to avoid deadlocks. The test spins up 10 threads for 3 items and asserts exactly 3 succeed (I checked it fails with the lock removed).

**Why reserve stock at order creation instead of at payment?**
Otherwise someone can pay for an item that's already gone, and you'd have to refund. The cost is held stock for abandoned carts, which `expire_orders` releases after 30 minutes. Stripe sessions also expire (`checkout.session.expired` webhook cancels the order too).

**What if the webhook is delivered twice, or after the user was redirected?**
`mark_paid` is idempotent (status check under a row lock). The success page also calls Stripe's API to sync, so the user doesn't see "pending" because of a race.

**What if payment arrives for an order that was already cancelled?**
We don't resurrect it (the stock may be gone). We log a warning so someone can refund. Next step would be an automatic refund via the API.

**Why integer cents?**
Float rounding errors, and Stripe's API uses the smallest currency unit.

**Why HTMX and not React?**
Less code, one source of truth for validation, no API/state sync. I still built a proper REST API, so a React/mobile client could be added.

**How is it secured?**
CSRF on all forms (HTMX sends the token header), Stripe webhook signature verification, UUID order URLs against enumeration, cart stores no prices, open-redirect check on `next`, staff-only dashboard, API throttling, secure cookies and a required `SECRET_KEY` outside debug mode.

**How would you scale it?**
Stateless web containers behind a load balancer (sessions to Redis or the DB), Postgres read replicas, Redis cache for catalog pages, Celery/ARQ for emails and order expiry, CDN for static files and images. The hot path is checkout; row locks only contend on the same product.

**N+1 queries?**
Cart loads products with one `in_bulk` query, list views use `select_related`/`prefetch_related`, the dashboard uses DB aggregation (`Sum`, `Count`, `TruncDate`).

**What would you improve?**
See "What I'd do next" in the README: background jobs, image uploads, refunds, caching.

## Things to be honest about if asked

- The mock gateway is for demos, and it's disabled automatically when Stripe keys are set.
- Order expiry is a management command, so it needs cron (or a task queue) in production.
- No email sending yet.
- Guest orders aren't linked to a user account afterwards.
