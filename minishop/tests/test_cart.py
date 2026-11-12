from cart.cart import MAX_PER_ITEM, Cart


def add(client, product, **extra):
    return client.post(f"/cart/add/{product.pk}/", **extra)


def test_add_and_totals(client, product, cheap_product):
    add(client, product)
    add(client, product)
    add(client, cheap_product)
    resp = client.get("/cart/")
    assert resp.status_code == 200
    assert resp.context["cart_count"] == 3
    assert resp.context["total_cents"] == 2 * 8900 + 500


def test_quantity_capped_by_stock(client, product):
    for _ in range(10):  # stock is 5
        add(client, product)
    assert client.get("/cart/").context["cart_count"] == 5


def test_quantity_capped_by_max_per_item(client, cheap_product):
    client.post(f"/cart/update/{cheap_product.pk}/", {"quantity": 999})
    assert client.get("/cart/").context["cart_count"] == MAX_PER_ITEM


def test_cannot_add_out_of_stock(client, product):
    product.stock = 0
    product.save()
    add(client, product)
    assert client.get("/cart/").context["cart_count"] == 0


def test_update_to_zero_removes(client, product):
    add(client, product)
    client.post(f"/cart/update/{product.pk}/", {"quantity": 0})
    assert client.get("/cart/").context["cart_count"] == 0


def test_update_garbage_quantity_is_ignored(client, product):
    add(client, product)
    resp = client.post(f"/cart/update/{product.pk}/", {"quantity": "abc"})
    assert resp.status_code == 302


def test_remove(client, product):
    add(client, product)
    client.post(f"/cart/remove/{product.pk}/")
    assert client.get("/cart/").context["cart_count"] == 0


def test_htmx_add_returns_badge_partial(client, product):
    resp = add(client, product, headers={"HX-Request": "true"})
    assert resp.status_code == 200
    assert b'id="cart-count"' in resp.content
    assert b">1<" in resp.content


def test_htmx_update_refreshes_navbar_badge(client, product):
    add(client, product)
    resp = client.post(f"/cart/update/{product.pk}/", {"quantity": 3}, headers={"HX-Request": "true"})
    assert b'hx-swap-oob="true"' in resp.content


def test_prices_come_from_db_not_session(client, product):
    add(client, product)
    product.price_cents = 1000
    product.save()
    assert client.get("/cart/").context["total_cents"] == 1000


def test_deactivated_product_drops_out_of_cart(client, product):
    add(client, product)
    product.is_active = False
    product.save()
    assert client.get("/cart/").context["lines"] == []


def test_open_redirect_is_blocked(client, product):
    resp = client.post(f"/cart/add/{product.pk}/", {"next": "https://evil.example/"})
    assert resp.url == "/cart/"


def test_cart_unit(rf, product):
    from django.contrib.sessions.backends.db import SessionStore

    request = rf.get("/")
    request.session = SessionStore()
    cart = Cart(request)
    cart.add(product, 2)
    assert len(cart) == 2
    assert cart.as_order_items() == {product.pk: 2}
    cart.clear()
    assert len(cart) == 0
