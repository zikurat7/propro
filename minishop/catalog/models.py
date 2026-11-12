from decimal import Decimal

from django.db import models
from django.db.models import Q
from django.urls import reverse


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ProductQuerySet(models.QuerySet["Product"]):
    def active(self) -> ProductQuerySet:
        return self.filter(is_active=True)

    def in_stock(self) -> ProductQuerySet:
        return self.filter(stock__gt=0)

    def search(self, term: str) -> ProductQuerySet:
        term = term.strip()
        if not term:
            return self
        return self.filter(Q(name__icontains=term) | Q(description__icontains=term))


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    # Money is stored as integer cents: no float/rounding bugs, and it is
    # exactly what Stripe expects for `unit_amount`.
    price_cents = models.PositiveIntegerField()
    stock = models.PositiveIntegerField(default=0)
    image_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "name"]
        constraints = [
            models.CheckConstraint(condition=Q(price_cents__gt=0), name="product_price_positive"),
        ]
        indexes = [models.Index(fields=["is_active", "category"])]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("catalog:product_detail", args=[self.slug])

    @property
    def price(self) -> Decimal:
        return Decimal(self.price_cents) / 100

    @property
    def in_stock(self) -> bool:
        return self.stock > 0
