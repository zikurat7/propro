from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("", views.order_list, name="list"),
    path("checkout/", views.checkout, name="checkout"),
    path("webhook/stripe/", views.stripe_webhook, name="stripe_webhook"),
    path("<uuid:public_id>/", views.order_detail, name="detail"),
    path("<uuid:public_id>/success/", views.order_success, name="success"),
    path("<uuid:public_id>/mock-pay/", views.mock_pay, name="mock_pay"),
]
