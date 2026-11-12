from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .models import Category, Product

PAGE_SIZE = 8


def product_list(request):
    products = Product.objects.active().select_related("category")
    categories = Category.objects.all()

    query = request.GET.get("q", "")
    products = products.search(query)

    active_category = None
    if slug := request.GET.get("category"):
        active_category = get_object_or_404(Category, slug=slug)
        products = products.filter(category=active_category)

    page = Paginator(products, PAGE_SIZE).get_page(request.GET.get("page"))
    context = {
        "page": page,
        "categories": categories,
        "active_category": active_category,
        "query": query,
    }
    return render(request, "catalog/product_list.html", context)


def product_detail(request, slug: str):
    product = get_object_or_404(Product.objects.active().select_related("category"), slug=slug)
    return render(request, "catalog/product_detail.html", {"product": product})
