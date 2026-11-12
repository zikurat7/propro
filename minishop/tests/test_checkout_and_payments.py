import json
from types import SimpleNamespace

import pytest
import stripe

from orders import services
from orders.models import Order


def checkout(client, email="buyer@example.com"):
    return client.post("/orders/checkout/", {"email": email})


def test_checkout_requires_items(client, db):
    resp = client.get("/orders/checkout/")
    assert resp.status_code == 302 and resp.url == "/"


def test_full_mock_flow(client, product):
    client.post(f"/cart/add/{product.pk}/")
    client.post(f"/cart/add/{product.pk}/")

    resp = checkout(client)
    order = Order.objects.get()
    assert resp.url == f"/orders/{order.public_id}/mock-pay/"
    assert order.total_cents == 17800
    assert client.get("/cart/").context["cart_count"] == 0  # cart cleared once order exists

    pay = client.post(resp.url, {"action": "pay"})
    assert pay.url == f"/orders/{order.public_id}/success/"
    order.refresh_from_db()
    assert order.status == Order.Status.PAID

    page = client.get(pay.url)
    assert b"Payment received" in page.content


def test_mock_cancel_restocks(client, product):
    client.post(f"/cart/add/{product.pk}/")
    resp = checkout(client)
    client.post(resp.url, {"action": "cancel"})
    product.refresh_from_db()
    assert product.stock == 5
    assert Order.objects.get().status == Order.Status.CANCELLED


def test_checkout_rejects_bad_email(client, product):
    client.post(f"/cart/add/{product.pk}/")
    resp = checkout(client, email="nope")
    assert resp.status_code == 200
    assert not Order.objects.exists()


def test_checkout_handles_stock_race(client, product):
    client.post(f"/cart/add/{product.pk}/")
    product.stock = 0  # someone else bought it between "add to cart" and "pay"
    product.save()
    resp = checkout(client)
    assert resp.url == "/cart/"
    assert not Order.objects.exists()


def test_guest_order_requires_uuid(client, product):
    order = services.create_order(items={product.pk: 1}, email="a@b.co")
    assert client.get(f"/orders/{order.public_id}/").status_code == 200
    assert client.get(f"/orders/{order.pk}/").status_code == 404  # no enumerating by integer id


def test_order_history_requires_login(client, user, product):
    assert client.get("/orders/").status_code == 302
    services.create_order(items={product.pk: 1}, email=user.email, user=user)
    client.force_login(user)
    assert len(client.get("/orders/").context["orders"]) == 1


def test_mock_pay_disabled_when_stripe_configured(client, product, settings):
    order = services.create_order(items={product.pk: 1}, email="a@b.co")
    settings.STRIPE_SECRET_KEY = "sk_test_x"
    assert client.get(f"/orders/{order.public_id}/mock-pay/").status_code == 404


# --- Stripe webhook ---------------------------------------------------------


@pytest.fixture
def stripe_event(monkeypatch):
    """Skip real signature verification; return whatever event the test wants."""
    holder = {}

    def fake_construct_event(payload, sig, secret):
        if sig != "valid":
            raise stripe.SignatureVerificationError("bad signature", sig)
        return json.loads(payload)

    monkeypatch.setattr(stripe.Webhook, "construct_event", fake_construct_event)
    return holder


def send_webhook(client, event_type, order, payment_status="paid", signature="valid"):
    body = {
        "type": event_type,
        "data": {
            "object": {
                "id": "cs_test_1",
                "client_reference_id": str(order.pk),
                "payment_status": payment_status,
            }
        },
    }
    return client.post(
        "/orders/webhook/stripe/",
        json.dumps(body),
        content_type="application/json",
        headers={"Stripe-Signature": signature},
    )


def test_webhook_rejects_bad_signature(client, product, stripe_event):
    order = services.create_order(items={product.pk: 1}, email="a@b.co")
    assert send_webhook(client, "checkout.session.completed", order, signature="forged").status_code == 400
    order.refresh_from_db()
    assert order.status == Order.Status.PENDING


def test_webhook_completed_marks_paid_and_is_idempotent(client, product, stripe_event):
    order = services.create_order(items={product.pk: 1}, email="a@b.co")
    for _ in range(2):  # Stripe retries
        assert send_webhook(client, "checkout.session.completed", order).status_code == 200
    order.refresh_from_db()
    assert order.status == Order.Status.PAID
    assert order.payment_reference == "cs_test_1"


def test_webhook_unpaid_completed_session_is_ignored(client, product, stripe_event):
    order = services.create_order(items={product.pk: 1}, email="a@b.co")
    send_webhook(client, "checkout.session.completed", order, payment_status="unpaid")
    order.refresh_from_db()
    assert order.status == Order.Status.PENDING


def test_webhook_expired_cancels_and_restocks(client, product, stripe_event):
    order = services.create_order(items={product.pk: 2}, email="a@b.co")
    send_webhook(client, "checkout.session.expired", order)
    order.refresh_from_db()
    product.refresh_from_db()
    assert order.status == Order.Status.CANCELLED
    assert product.stock == 5


def test_webhook_unknown_order_is_acknowledged(client, db, stripe_event):
    ghost = SimpleNamespace(pk=99999)
    assert send_webhook(client, "checkout.session.completed", ghost).status_code == 200


def test_webhook_get_not_allowed(client, db):
    assert client.get("/orders/webhook/stripe/").status_code == 405


# --- Stripe gateway ---------------------------------------------------------


def test_stripe_gateway_builds_checkout_session(rf, product, settings, monkeypatch):
    from orders.payments import StripeGateway

    settings.STRIPE_SECRET_KEY = "sk_test_x"
    order = services.create_order(items={product.pk: 2}, email="a@b.co")
    captured = {}

    class FakeSessions:
        def create(self, params):
            captured.update(params)
            return SimpleNamespace(id="cs_test_42", url="https://checkout.stripe.test/pay")

    gateway = StripeGateway()
    monkeypatch.setattr(gateway, "client", SimpleNamespace(checkout=SimpleNamespace(sessions=FakeSessions())))

    url = gateway.start_checkout(order, rf.get("/"))

    assert url == "https://checkout.stripe.test/pay"
    order.refresh_from_db()
    assert order.payment_reference == "cs_test_42"
    assert captured["client_reference_id"] == str(order.pk)
    line = captured["line_items"][0]
    assert line["quantity"] == 2 and line["price_data"]["unit_amount"] == 8900
