"""`python manage.py seed_demo` — fills the store with sample data (safe to re-run)."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from catalog.models import Category, Product

DEMO = {
    "Keyboards": [
        ("Mechanical Keyboard 75%", 8900, 25, "Hot-swappable switches, gasket mount, PBT keycaps."),
        ("Wireless Slim Keyboard", 4900, 40, "Low-profile, 3 device pairing, 4-month battery."),
        ("Split Ergonomic Keyboard", 14900, 8, "Tented split layout with programmable layers."),
    ],
    "Mice": [
        ("Ergonomic Vertical Mouse", 3900, 30, "Reduces wrist strain. Works on Mac, Linux, Windows."),
        ("Precision Gaming Mouse", 5900, 20, "26K DPI sensor, 60g, 70-hour battery."),
        ("Travel Mouse", 1900, 60, "Pocket-sized Bluetooth mouse."),
    ],
    "Monitors": [
        ('27" 4K IPS Monitor', 32900, 12, "99% sRGB, USB-C 90W power delivery."),
        ('34" Ultrawide Curved', 44900, 5, "3440x1440, 144Hz, great for split-screen coding."),
        ('24" Budget 1080p', 11900, 35, "Simple, reliable, VESA mountable."),
    ],
    "Accessories": [
        ("USB-C Dock 11-in-1", 7900, 18, "Dual HDMI, ethernet, SD card, 100W passthrough."),
        ("Aluminium Laptop Stand", 3500, 50, "Foldable, 6 height settings."),
        ("Desk Mat XL", 2500, 0, "Water-resistant, 90x40cm. (Out of stock on purpose, for demos.)"),
        ("Webcam 1080p", 4500, 22, "Autofocus, dual mics, privacy shutter."),
    ],
}


class Command(BaseCommand):
    help = "Create demo categories, products and an admin user (admin / admin)."

    def handle(self, *args, **options):
        created = 0
        for category_name, products in DEMO.items():
            category, _ = Category.objects.get_or_create(
                slug=slugify(category_name), defaults={"name": category_name}
            )
            for name, price_cents, stock, description in products:
                _, was_created = Product.objects.get_or_create(
                    slug=slugify(name),
                    defaults={
                        "category": category,
                        "name": name,
                        "price_cents": price_cents,
                        "stock": stock,
                        "description": description,
                    },
                )
                created += was_created

        User = get_user_model()
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@example.com", "admin")
            self.stdout.write("Created superuser admin / admin (local demo only!)")

        self.stdout.write(self.style.SUCCESS(f"Seeded {created} new products."))
