"""Real concurrency test. Needs Postgres (SQLite ignores row locks), so it is skipped on SQLite."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import connection, connections

from orders import services
from orders.models import Order

pytestmark = pytest.mark.skipif(
    connection.vendor != "postgresql", reason="select_for_update needs a real database like Postgres"
)


@pytest.mark.django_db(transaction=True)
def test_concurrent_checkouts_never_oversell(product):
    product.stock = 3
    product.save()

    def try_buy(i: int) -> bool:
        try:
            services.create_order(items={product.pk: 1}, email=f"buyer{i}@example.com")
            return True
        except services.OutOfStock:
            return False
        finally:
            connections.close_all()  # each thread has its own connection

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(try_buy, range(10)))

    product.refresh_from_db()
    assert sum(results) == 3
    assert product.stock == 0
    assert Order.objects.count() == 3
