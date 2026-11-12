"""Order business logic. Views and the API both call these functions.

Stock is *reserved* when the order is created (decremented inside a transaction
with row locks) and *released* if the order is cancelled or expires unpaid.
That way two people can never buy the last item.
"""

import logging
from collections.abc import Mapping
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from catalog.models import Product

from .models import Order, OrderItem

logger = logging.getLogger(__name__)


class OrderError(Exception):
    """Base class for errors that are the customer's problem, not a bug."""


class EmptyOrder(OrderError):
    pass


class ProductUnavailable(OrderError):
    pass


class OutOfStock(OrderError):
    def __init__(self, product: Product) -> None:
        super().__init__(f"Not enough stock for {product.name} (only {product.stock} left).")
        self.product = product


@transaction.atomic
def create_order(*, items: Mapping[int, int], email: str, user=None) -> Order:
    """Create a pending order and reserve stock. ``items`` maps product id -> quantity.

    Rows are locked with ``select_for_update`` in primary-key order, so concurrent
    checkouts serialize on the product rows and can't deadlock each other.
    Raising anywhere rolls back the whole transaction, including stock changes.
    """
    if not items or any(qty < 1 for qty in items.values()):
        raise EmptyOrder("Your order has no items.")

    products = {
        p.pk: p
        for p in Product.objects.select_for_update().filter(pk__in=items, is_active=True).order_by("pk")
    }
    if missing := set(items) - set(products):
        raise ProductUnavailable(f"Products no longer available: {sorted(missing)}")

    order = Order.objects.create(email=email, user=user if getattr(user, "is_authenticated", False) else None)
    order_items = []
    for pk in sorted(items):
        product, quantity = products[pk], items[pk]
        if product.stock < quantity:
            raise OutOfStock(product)
        product.stock -= quantity
        product.save(update_fields=["stock"])
        order_items.append(
            OrderItem(
                order=order,
                product=product,
                product_name=product.name,
                unit_price_cents=product.price_cents,
                quantity=quantity,
            )
        )
    OrderItem.objects.bulk_create(order_items)
    order.total_cents = sum(i.subtotal_cents for i in order_items)
    order.save(update_fields=["total_cents"])
    return order


@transaction.atomic
def mark_paid(order_id: int, payment_reference: str = "") -> Order:
    """Idempotent: Stripe retries webhooks, so calling this twice must be harmless."""
    order = Order.objects.select_for_update().get(pk=order_id)
    if order.status == Order.Status.PAID:
        return order
    if order.status == Order.Status.CANCELLED:
        # Paid after we released the stock. Don't resurrect it silently; flag for a human/refund.
        logger.warning("Payment received for cancelled order %s: needs manual review/refund", order.pk)
        return order
    order.status = Order.Status.PAID
    order.paid_at = timezone.now()
    if payment_reference:
        order.payment_reference = payment_reference
    order.save(update_fields=["status", "paid_at", "payment_reference"])
    return order


@transaction.atomic
def cancel_order(order_id: int) -> Order:
    """Cancel a pending order and put its stock back. No-op unless still pending."""
    order = Order.objects.select_for_update().get(pk=order_id)
    if order.status != Order.Status.PENDING:
        return order
    for item in order.items.all():
        Product.objects.filter(pk=item.product_id).update(stock=F("stock") + item.quantity)
    order.status = Order.Status.CANCELLED
    order.save(update_fields=["status"])
    return order


def expire_stale_orders() -> int:
    """Cancel pending orders older than ORDER_HOLD_MINUTES. Returns how many."""
    cutoff = timezone.now() - timedelta(minutes=settings.ORDER_HOLD_MINUTES)
    stale_ids = list(
        Order.objects.filter(status=Order.Status.PENDING, created_at__lt=cutoff).values_list("pk", flat=True)
    )
    for order_id in stale_ids:
        cancel_order(order_id)
    return len(stale_ids)
