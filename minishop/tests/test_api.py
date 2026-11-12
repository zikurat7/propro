import pytest
from rest_framework.test import APIClient

from orders import services


@pytest.fixture
def api():
    return APIClient()


def test_product_list_is_public_and_filterable(api, product, cheap_product):
    resp = api.get("/api/products/", {"q": "keycap"})
    assert resp.status_code == 200
    assert [p["slug"] for p in resp.data["results"]] == ["keycap"]


def test_product_ordering_and_in_stock_filter(api, product, cheap_product):
    product.stock = 0
    product.save()
    resp = api.get("/api/products/", {"in_stock": "true", "ordering": "price_cents"})
    assert [p["slug"] for p in resp.data["results"]] == ["keycap"]


def test_product_detail_by_slug(api, product):
    resp = api.get(f"/api/products/{product.slug}/")
    assert resp.status_code == 200
    assert resp.data["price_cents"] == 8900 and resp.data["price"] == "89.00"


def test_categories(api, category):
    assert api.get("/api/categories/").data[0]["slug"] == "keyboards"


def test_orders_require_auth(api, db):
    assert api.get("/api/orders/").status_code == 403
    assert api.post("/api/orders/", {"items": []}, format="json").status_code == 403


def test_create_order(api, user, product):
    api.force_authenticate(user)
    resp = api.post("/api/orders/", {"items": [{"product": product.pk, "quantity": 2}]}, format="json")
    assert resp.status_code == 201
    assert resp.data["total_cents"] == 17800
    assert resp.data["checkout_url"].endswith("/mock-pay/")
    product.refresh_from_db()
    assert product.stock == 3


def test_create_order_out_of_stock_returns_409(api, user, product):
    api.force_authenticate(user)
    resp = api.post("/api/orders/", {"items": [{"product": product.pk, "quantity": 6}]}, format="json")
    assert resp.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"items": []},
        {"items": [{"product": 1, "quantity": 0}]},
        {"items": [{"product": 1, "quantity": 1}, {"product": 1, "quantity": 2}]},
        {},
    ],
)
def test_create_order_validation(api, user, product, payload):
    api.force_authenticate(user)
    assert api.post("/api/orders/", payload, format="json").status_code == 400


def test_unknown_product_is_400(api, user, db):
    api.force_authenticate(user)
    resp = api.post("/api/orders/", {"items": [{"product": 424242, "quantity": 1}]}, format="json")
    assert resp.status_code == 400


def test_users_only_see_their_own_orders(api, user, staff, product):
    mine = services.create_order(items={product.pk: 1}, email=user.email, user=user)
    services.create_order(items={product.pk: 1}, email=staff.email, user=staff)

    api.force_authenticate(user)
    listing = api.get("/api/orders/")
    assert [o["id"] for o in listing.data["results"]] == [str(mine.public_id)]

    api.force_authenticate(staff)
    assert api.get(f"/api/orders/{mine.public_id}/").status_code == 404


def test_basic_auth_works(api, user, product):
    api.credentials(HTTP_AUTHORIZATION="Basic c2FtOnB3LTEyMzQ1LXh5eg==")  # sam:pw-12345-xyz
    assert api.get("/api/orders/").status_code == 200


def test_openapi_schema_builds(api, db):
    resp = api.get("/api/schema/")
    assert resp.status_code == 200
    assert b"/api/products/" in resp.content
