"""Settings used by pytest: real settings, plus safe defaults so tests need no env setup."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key")
os.environ["STRIPE_SECRET_KEY"] = ""  # tests never talk to Stripe unless they patch it explicitly

from .settings import *  # noqa: E402, F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # faster tests
MIDDLEWARE = [m for m in MIDDLEWARE if "whitenoise" not in m]  # noqa: F405  (no collected static dir in tests)
