from rest_framework import serializers

from cart.cart import MAX_PER_ITEM
from catalog.models import Category, Product
from orders.models import Order, OrderItem


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class ProductSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "category",
            "price",
            "price_cents",
            "stock",
            "image_url",
        ]


class OrderItemSerializer(serializers.ModelSerializer):
    subtotal_cents = serializers.IntegerField(read_only=True)

    class Meta:
        model = OrderItem
        fields = ["product", "product_name", "unit_price_cents", "quantity", "subtotal_cents"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    id = serializers.UUIDField(source="public_id", read_only=True)

    class Meta:
        model = Order
        fields = ["id", "status", "email", "total_cents", "created_at", "paid_at", "items"]


class OrderLineInputSerializer(serializers.Serializer):
    product = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=MAX_PER_ITEM)


class OrderCreateSerializer(serializers.Serializer):
    items = OrderLineInputSerializer(many=True, allow_empty=False)

    def validate_items(self, value):
        product_ids = [line["product"] for line in value]
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError("Each product may only appear once.")
        return value


class OrderCreatedSerializer(OrderSerializer):
    checkout_url = serializers.CharField(read_only=True)

    class Meta(OrderSerializer.Meta):
        fields = [*OrderSerializer.Meta.fields, "checkout_url"]
