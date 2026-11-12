from django.contrib.auth import get_user_model
from django.core.management import call_command


def test_signup_logs_in(client, db):
    resp = client.post(
        "/accounts/signup/",
        {
            "username": "newbie",
            "email": "n@e.co",
            "password1": "tr0ub4dor&3-long",
            "password2": "tr0ub4dor&3-long",
        },
    )
    assert resp.status_code == 302
    assert get_user_model().objects.get(username="newbie").email == "n@e.co"
    assert "_auth_user_id" in client.session


def test_login_and_logout(client, user):
    assert client.post("/accounts/login/", {"username": "sam", "password": "pw-12345-xyz"}).status_code == 302
    assert client.post("/accounts/logout/").status_code == 302
    assert "_auth_user_id" not in client.session


def test_seed_demo_is_idempotent(db):
    from catalog.models import Product

    call_command("seed_demo", verbosity=0)
    count = Product.objects.count()
    call_command("seed_demo", verbosity=0)
    assert count > 0 and Product.objects.count() == count


def test_expire_orders_command(product, capsys):
    call_command("expire_orders")
    assert "Expired 0" in capsys.readouterr().out
