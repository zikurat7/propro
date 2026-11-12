import pytest
from django.db import IntegrityError, transaction

from catalog.models import Product


def test_price_property_converts_cents(product):
    assert str(product.price) == "89"
    assert product.price_cents == 8900


def test_db_rejects_non_positive_price(category):
    with pytest.raises(IntegrityError), transaction.atomic():
        Product.objects.create(category=category, name="Free", slug="free", price_cents=0)


def test_search_matches_name_and_description(product, cheap_product):
    assert list(Product.objects.search("mech")) == [product]
    cheap_product.description = "Fits mechanical boards"
    cheap_product.save()
    assert set(Product.objects.search("mech")) == {product, cheap_product}


def test_active_excludes_hidden(product):
    product.is_active = False
    product.save()
    assert not Product.objects.active().exists()


def test_product_list_filters_by_category_and_query(client, product, cheap_product):
    resp = client.get("/", {"q": "keycap"})
    assert resp.status_code == 200
    names = [p.name for p in resp.context["page"]]
    assert names == ["Keycap"]


def test_product_list_unknown_category_404(client, db):
    assert client.get("/", {"category": "nope"}).status_code == 404


def test_product_detail(client, product):
    resp = client.get(product.get_absolute_url())
    assert resp.status_code == 200
    assert b"Mech Keyboard" in resp.content


def test_inactive_product_detail_404(client, product):
    product.is_active = False
    product.save()
    assert client.get(product.get_absolute_url()).status_code == 404
