from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Avg, Count, F, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone

from catalog.models import Product
from orders.models import Order, OrderItem

LOW_STOCK_THRESHOLD = 5
DAYS = 30


def revenue_by_day(days: int = DAYS) -> list[dict]:
    """Paid revenue per calendar day, with zero-filled gaps so the chart has no holes."""
    since = timezone.now() - timedelta(days=days - 1)
    rows = (
        Order.objects.filter(status=Order.Status.PAID, paid_at__gte=since)
        .annotate(day=TruncDate("paid_at"))
        .values("day")
        .annotate(revenue=Sum("total_cents"), orders=Count("id"))
    )
    by_day = {row["day"]: row for row in rows}
    today = timezone.now().date()
    series = []
    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        row = by_day.get(day)
        series.append(
            {
                "day": day.isoformat(),
                "revenue": (row["revenue"] if row else 0) / 100,
                "orders": row["orders"] if row else 0,
            }
        )
    return series


@staff_member_required
def dashboard(request):
    paid = Order.objects.filter(status=Order.Status.PAID)
    totals = paid.aggregate(revenue=Sum("total_cents"), orders=Count("id"), average=Avg("total_cents"))

    top_products = (
        OrderItem.objects.filter(order__status=Order.Status.PAID)
        .values("product__name")
        .annotate(units=Sum("quantity"), revenue=Sum(F("quantity") * F("unit_price_cents")))
        .order_by("-revenue")[:5]
    )
    context = {
        "revenue_cents": totals["revenue"] or 0,
        "paid_orders": totals["orders"],
        "average_cents": int(totals["average"] or 0),
        "pending_orders": Order.objects.filter(status=Order.Status.PENDING).count(),
        "top_products": top_products,
        "low_stock": Product.objects.active().filter(stock__lte=LOW_STOCK_THRESHOLD).order_by("stock")[:10],
        "recent_orders": Order.objects.all()[:8],
        "series": revenue_by_day(),
        "low_stock_threshold": LOW_STOCK_THRESHOLD,
    }
    return render(request, "dashboard/dashboard.html", context)
