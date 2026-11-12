"""Payment gateways. Real Stripe Checkout when keys are configured, otherwise a mock.

Both implement the same tiny interface, so the rest of the app doesn't care.
"""

import logging
import time
from typing import Protocol

import stripe
from django.conf import settings
from django.urls import reverse

from .models import Order
from .services import mark_paid

logger = logging.getLogger(__name__)


class Gateway(Protocol):
    def start_checkout(self, order: Order, request) -> str:
        """Return the URL to send the customer to in order to pay."""

    def sync(self, order: Order) -> None:
        """Ask the provider whether the order was paid (fallback if the webhook is late)."""


class StripeGateway:
    def __init__(self) -> None:
        self.client = stripe.StripeClient(settings.STRIPE_SECRET_KEY)

    def start_checkout(self, order: Order, request) -> str:
        detail_url = request.build_absolute_uri(reverse("orders:success", args=[order.public_id]))
        session = self.client.checkout.sessions.create(
            params={
                "mode": "payment",
                "client_reference_id": str(order.pk),
                "customer_email": order.email,
                "line_items": [
                    {
                        "quantity": item.quantity,
                        "price_data": {
                            "currency": settings.CURRENCY,
                            "unit_amount": item.unit_price_cents,
                            "product_data": {"name": item.product_name},
                        },
                    }
                    for item in order.items.all()
                ],
                "success_url": detail_url,
                "cancel_url": request.build_absolute_uri(reverse("orders:detail", args=[order.public_id])),
                # Stripe's minimum is 30 minutes; keep in sync with ORDER_HOLD_MINUTES.
                "expires_at": int(time.time()) + max(settings.ORDER_HOLD_MINUTES, 30) * 60,
            }
        )
        order.payment_reference = session.id
        order.save(update_fields=["payment_reference"])
        return session.url

    def sync(self, order: Order) -> None:
        if not order.payment_reference.startswith("cs_"):
            return
        session = self.client.checkout.sessions.retrieve(order.payment_reference)
        if session.payment_status == "paid":
            mark_paid(order.pk)


class MockGateway:
    """Fake payment page so the full flow is demoable without a Stripe account."""

    def start_checkout(self, order: Order, request) -> str:
        return reverse("orders:mock_pay", args=[order.public_id])

    def sync(self, order: Order) -> None:
        return None


def stripe_enabled() -> bool:
    return bool(settings.STRIPE_SECRET_KEY)


def get_gateway() -> Gateway:
    return StripeGateway() if stripe_enabled() else MockGateway()
