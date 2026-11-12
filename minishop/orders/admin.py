from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["product", "product_name", "unit_price_cents", "quantity"]
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "email", "status", "total_cents", "created_at", "paid_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["email", "payment_reference", "public_id"]
    readonly_fields = ["public_id", "user", "total_cents", "payment_reference", "created_at", "paid_at"]
    inlines = [OrderItemInline]
