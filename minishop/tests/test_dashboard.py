import pytest
from django.utils import timezone

from dashboard.views import revenue_by_day
from orders import services
from orders.models import Order


def test_dashboard_requires_staff(client, user):
    assert client.get("/dashboard/").status_code == 302  # to admin login
    client.force_login(user)
    assert client.get("/dashboard/").status_code == 302


def test_dashboard_totals(client, staff, product, cheap_product):
    paid = services.create_order(items={product.pk: 2}, email="a@b.co")
    services.mark_paid(paid.pk)
    services.create_order(items={cheap_product.pk: 1}, email="c@d.co")  # pending: not counted as revenue

    client.force_login(staff)
    resp = client.get("/dashboard/")
    assert resp.status_code == 200
    ctx = resp.context
    assert ctx["revenue_cents"] == 17800
    assert ctx["paid_orders"] == 1
    assert ctx["pending_orders"] == 1
    assert ctx["average_cents"] == 17800
    assert list(ctx["top_products"])[0]["units"] == 2


def test_dashboard_low_stock_lists_scarce_products(client, staff, product, cheap_product):
    client.force_login(staff)
    names = [p.name for p in client.get("/dashboard/").context["low_stock"]]
    assert names == ["Mech Keyboard"]  # stock 5 <= threshold, keycaps (100) are not


def test_dashboard_empty_state(client, staff, db):
    client.force_login(staff)
    assert client.get("/dashboard/").status_code == 200


@pytest.mark.django_db
def test_revenue_series_is_zero_filled(product):
    order = services.create_order(items={product.pk: 1}, email="a@b.co")
    services.mark_paid(order.pk)
    series = revenue_by_day(days=7)
    assert len(series) == 7
    assert series[-1] == {"day": timezone.now().date().isoformat(), "revenue": 89.0, "orders": 1}
    assert all(day["revenue"] == 0 for day in series[:-1])
    assert Order.objects.count() == 1
