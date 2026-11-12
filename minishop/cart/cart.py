from collections.abc import Iterator
from dataclasses import dataclass

from catalog.models import Product

MAX_PER_ITEM = 20


@dataclass(frozen=True, slots=True)
class CartLine:
    product: Product
    quantity: int

    @property
    def subtotal_cents(self) -> int:
        return self.product.price_cents * self.quantity


class Cart:
    """Session-backed cart. Stores only ``{product_id: quantity}``.

    Prices are never stored in the session: they are looked up from the DB each
    time, so a price change (or a tampered session) can't give a stale price.
    """

    SESSION_KEY = "cart"

    def __init__(self, request) -> None:
        self._session = request.session
        self._items: dict[str, int] = self._session.setdefault(self.SESSION_KEY, {})

    def _save(self) -> None:
        self._session.modified = True

    def add(self, product: Product, quantity: int = 1) -> None:
        current = self._items.get(str(product.pk), 0)
        self.set_quantity(product, current + quantity)

    def set_quantity(self, product: Product, quantity: int) -> None:
        quantity = min(quantity, product.stock, MAX_PER_ITEM)
        if quantity <= 0:
            self.remove(product.pk)
            return
        self._items[str(product.pk)] = quantity
        self._save()

    def remove(self, product_id: int) -> None:
        self._items.pop(str(product_id), None)
        self._save()

    def clear(self) -> None:
        self._items.clear()
        self._save()

    def lines(self) -> list[CartLine]:
        """One query for all products; inactive/deleted products silently drop out."""
        products = Product.objects.active().in_bulk([int(pk) for pk in self._items])
        return [
            CartLine(product=products[pk], quantity=qty)
            for pk, qty in ((int(k), v) for k, v in self._items.items())
            if pk in products
        ]

    def as_order_items(self) -> dict[int, int]:
        return {line.product.pk: line.quantity for line in self.lines()}

    def __iter__(self) -> Iterator[CartLine]:
        return iter(self.lines())

    def __len__(self) -> int:
        return sum(self._items.values())

    @property
    def total_cents(self) -> int:
        return sum(line.subtotal_cents for line in self.lines())
