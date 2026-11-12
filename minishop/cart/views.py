from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from catalog.models import Product

from .cart import Cart


def _is_htmx(request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _cart_context(request) -> dict:
    cart = Cart(request)
    return {"cart": cart, "lines": cart.lines(), "cart_count": len(cart), "total_cents": cart.total_cents}


def cart_detail(request):
    return render(request, "cart/cart.html", _cart_context(request))


@require_POST
def cart_add(request, product_id: int):
    product = get_object_or_404(Product.objects.active(), pk=product_id)
    cart = Cart(request)
    if not product.in_stock:
        messages.error(request, f"Sorry, {product.name} is out of stock.")
    else:
        cart.add(product)
    if _is_htmx(request):
        return render(request, "cart/_badge.html", {"cart_count": len(cart)})
    next_url = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_url = "cart:detail"
    return redirect(next_url)


@require_POST
def cart_update(request, product_id: int):
    product = get_object_or_404(Product.objects.active(), pk=product_id)
    try:
        quantity = int(request.POST.get("quantity", 0))
    except ValueError:
        quantity = 0
    Cart(request).set_quantity(product, quantity)
    return _render_cart(request)


@require_POST
def cart_remove(request, product_id: int):
    Cart(request).remove(product_id)
    return _render_cart(request)


def _render_cart(request):
    if _is_htmx(request):
        # oob_badge: also refresh the navbar counter, which lives outside the swapped #cart div
        return render(request, "cart/_cart.html", {**_cart_context(request), "oob_badge": True})
    return redirect("cart:detail")
