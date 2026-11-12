from datetime import timedelta

import pytest
from django.utils import timezone

from orders import services
from orders.models import Order


def test_create_order_reserves_stock_and_snapshots_prices(product, cheap_product):
    order = services.create_order(items={product.pk: 2, cheap_product.pk: 3}, email="a@b.co")

    product.refresh_from_db()
    cheap_product.refresh_from_db()
    assert (product.stock, cheap_product.stock) == (3, 97)
    assert order.status == Order.Status.PENDING
    assert order.total_cents == 2 * 8900 + 3 * 500

    product.price_cents = 99999
    product.save()
    assert order.items.get(product=product).unit_price_cents == 8900


def test_out_of_stock_rolls_back_everything(product, cheap_product):
    with pytest.raises(services.OutOfStock):
        services.create_order(items={cheap_product.pk: 1, product.pk: 6}, email="a@b.co")  # stock is 5

    cheap_product.refresh_from_db()
    assert cheap_product.stock == 100  # the earlier decrement was rolled back too
    assert not Order.objects.exists()


def test_cannot_buy_last_item_twice(product):
    product.stock = 1
    product.save()
    services.create_order(items={product.pk: 1}, email="a@b.co")
    with pytest.raises(services.OutOfStock):
        services.create_order(items={product.pk: 1}, email="c@d.co")


def test_empty_and_invalid_orders(product):
    with pytest.raises(services.EmptyOrder):
        services.create_order(items={}, email="a@b.co")
    with pytest.raises(services.EmptyOrder):
        services.create_order(items={product.pk: 0}, email="a@b.co")


def test_inactive_product_unavailable(product):
    product.is_active = False
    product.save()
    with pytest.raises(services.ProductUnavailable):
        services.create_order(items={product.pk: 1}, email="a@b.co")


def test_mark_paid_is_idempotent(product):
    order = services.create_order(items={product.pk: 1}, email="a@b.co")
    first = services.mark_paid(order.pk, "cs_123")
    paid_at = first.paid_at
    second = services.mark_paid(order.pk, "cs_123")
    assert second.status == Order.Status.PAID
    assert second.paid_at == paid_at


def test_cancel_restocks_once(product):
    order = services.create_order(items={product.pk: 2}, email="a@b.co")
    services.cancel_order(order.pk)
    services.cancel_order(order.pk)  # second call must not restock again
    product.refresh_from_db()
    assert product.stock == 5


def test_cannot_cancel_paid_order(product):
    order = services.create_order(items={product.pk: 2}, email="a@b.co")
    services.mark_paid(order.pk)
    services.cancel_order(order.pk)
    product.refresh_from_db()
    assert Order.objects.get().status == Order.Status.PAID
    assert product.stock == 3


def test_late_payment_on_cancelled_order_does_not_resurrect_it(product):
    order = services.create_order(items={product.pk: 1}, email="a@b.co")
    services.cancel_order(order.pk)
    assert services.mark_paid(order.pk).status == Order.Status.CANCELLED


def test_expire_stale_orders(product):
    old = services.create_order(items={product.pk: 2}, email="old@b.co")
    fresh = services.create_order(items={product.pk: 1}, email="new@b.co")
    Order.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(hours=2))

    assert services.expire_stale_orders() == 1
    old.refresh_from_db()
    fresh.refresh_from_db()
    product.refresh_from_db()
    assert (old.status, fresh.status) == (Order.Status.CANCELLED, Order.Status.PENDING)
    assert product.stock == 4  # 5 - 2 - 1 + 2 released
