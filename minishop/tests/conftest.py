import pytest
from django.contrib.auth import get_user_model

from catalog.models import Category, Product


@pytest.fixture
def category(db):
    return Category.objects.create(name="Keyboards", slug="keyboards")


@pytest.fixture
def product(category):
    return Product.objects.create(
        category=category, name="Mech Keyboard", slug="mech-keyboard", price_cents=8900, stock=5
    )


@pytest.fixture
def cheap_product(category):
    return Product.objects.create(category=category, name="Keycap", slug="keycap", price_cents=500, stock=100)


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user("sam", "sam@example.com", "pw-12345-xyz")


@pytest.fixture
def staff(db):
    return get_user_model().objects.create_user("boss", "boss@example.com", "pw-12345-xyz", is_staff=True)
