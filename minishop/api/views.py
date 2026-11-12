from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from catalog.models import Category, Product
from orders import services
from orders.models import Order
from orders.payments import get_gateway

from .serializers import (
    CategorySerializer,
    OrderCreatedSerializer,
    OrderCreateSerializer,
    OrderSerializer,
    ProductSerializer,
)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    pagination_class = None
    lookup_field = "slug"


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """Browse products. Filters: ``?category=<slug>``, ``?q=<text>``, ``?in_stock=true``."""

    serializer_class = ProductSerializer
    lookup_field = "slug"
    filter_backends = [OrderingFilter]
    ordering_fields = ["price_cents", "name", "created_at"]

    def get_queryset(self):
        qs = Product.objects.active().select_related("category")
        params = self.request.query_params
        if category := params.get("category"):
            qs = qs.filter(category__slug=category)
        if q := params.get("q"):
            qs = qs.search(q)
        if params.get("in_stock", "").lower() in {"1", "true"}:
            qs = qs.in_stock()
        return qs


class OrderViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Authenticated users can place orders and see their own."""

    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer
    lookup_field = "public_id"

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related("items")

    @extend_schema(request=OrderCreateSerializer, responses={201: OrderCreatedSerializer})
    def create(self, request, *args, **kwargs):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        items = {line["product"]: line["quantity"] for line in serializer.validated_data["items"]}

        try:
            order = services.create_order(items=items, email=request.user.email, user=request.user)
        except services.OutOfStock as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except services.OrderError as exc:
            raise ValidationError({"detail": str(exc)}) from exc

        order.checkout_url = request.build_absolute_uri(get_gateway().start_checkout(order, request))
        return Response(OrderCreatedSerializer(order).data, status=status.HTTP_201_CREATED)
