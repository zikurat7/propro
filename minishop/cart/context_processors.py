from .cart import Cart


def cart(request) -> dict[str, int]:
    """Expose the cart item count to every template (for the navbar badge)."""
    return {"cart_count": len(Cart(request))}
