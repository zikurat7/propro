import logging

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from cart.cart import Cart

from . import services
from .models import Order
from .payments import get_gateway, stripe_enabled

logger = logging.getLogger(__name__)


def checkout(request):
    cart = Cart(request)
    lines = cart.lines()
    if not lines:
        messages.info(request, "Your cart is empty.")
        return redirect("catalog:product_list")

    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        if "@" not in email:
            messages.error(request, "Please enter a valid email address.")
        else:
            try:
                order = services.create_order(items=cart.as_order_items(), email=email, user=request.user)
            except services.OrderError as exc:
                messages.error(request, str(exc))
                return redirect("cart:detail")
            cart.clear()
            return redirect(get_gateway().start_checkout(order, request))

    initial_email = getattr(request.user, "email", "")
    context = {"lines": lines, "total_cents": cart.total_cents, "email": initial_email}
    return render(request, "orders/checkout.html", context)


def order_detail(request, public_id):
    order = get_object_or_404(Order.objects.prefetch_related("items"), public_id=public_id)
    return render(request, "orders/order_detail.html", {"order": order})


def order_success(request, public_id):
    """Where Stripe sends the customer back. The webhook is the source of truth,
    but it can arrive after the redirect, so we also ask Stripe directly."""
    order = get_object_or_404(Order.objects.prefetch_related("items"), public_id=public_id)
    if order.status == Order.Status.PENDING:
        get_gateway().sync(order)
        order.refresh_from_db()
    return render(request, "orders/order_detail.html", {"order": order, "just_paid": True})


@login_required
def order_list(request):
    orders = request.user.orders.prefetch_related("items")
    return render(request, "orders/order_list.html", {"orders": orders})


def mock_pay(request, public_id):
    """Stand-in for Stripe's hosted page. Only exists when Stripe isn't configured."""
    if stripe_enabled():
        raise Http404
    order = get_object_or_404(Order, public_id=public_id)
    if request.method == "POST" and order.status == Order.Status.PENDING:
        if request.POST.get("action") == "pay":
            services.mark_paid(order.pk, payment_reference=f"mock_{order.public_id}")
            return redirect("orders:success", public_id=order.public_id)
        services.cancel_order(order.pk)
        return redirect("orders:detail", public_id=order.public_id)
    return render(request, "orders/mock_pay.html", {"order": order})


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Stripe -> us. The signature check is what proves the request is really from Stripe."""
    signature = request.headers.get("Stripe-Signature", "")
    try:
        event = stripe.Webhook.construct_event(request.body, signature, settings.STRIPE_WEBHOOK_SECRET)
    except ValueError, stripe.SignatureVerificationError:
        return HttpResponseBadRequest("invalid payload or signature")

    session = event["data"]["object"]
    order_id = session.get("client_reference_id")
    if not order_id:
        return HttpResponse(status=200)  # not one of ours; acknowledge so Stripe stops retrying

    try:
        match event["type"]:
            case "checkout.session.completed" | "checkout.session.async_payment_succeeded":
                if session.get("payment_status") == "paid":
                    services.mark_paid(int(order_id), payment_reference=session.get("id", ""))
            case "checkout.session.expired" | "checkout.session.async_payment_failed":
                services.cancel_order(int(order_id))
    except Order.DoesNotExist:
        logger.warning("Webhook %s references unknown order %s", event["type"], order_id)
    return HttpResponse(status=200)
