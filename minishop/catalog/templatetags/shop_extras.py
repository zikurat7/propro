from django import template

register = template.Library()


@register.filter
def money(cents: int) -> str:
    """Format integer cents as a dollar string: 1999 -> $19.99."""
    return f"${int(cents) / 100:,.2f}"
