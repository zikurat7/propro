import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from catalog.models import Product


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending payment"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"

    # Public, unguessable id used in URLs so guests can view their order
    # without anyone being able to enumerate /orders/1, /orders/2, ...
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="orders"
    )
    email = models.EmailField()
    status = models.CharField(max_length=10, choices=Status, default=Status.PENDING)
    total_cents = models.PositiveIntegerField(default=0)
    payment_reference = models.CharField(max_length=255, blank=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self) -> str:
        return f"Order #{self.pk} ({self.status})"

    def get_absolute_url(self) -> str:
        return reverse("orders:detail", args=[self.public_id])


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="+")
    # Name and price are snapshotted: later catalog edits must not rewrite history.
    product_name = models.CharField(max_length=200)
    unit_price_cents = models.PositiveIntegerField()
    quantity = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="orderitem_quantity_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.quantity} x {self.product_name}"

    @property
    def subtotal_cents(self) -> int:
        return self.unit_price_cents * self.quantity
