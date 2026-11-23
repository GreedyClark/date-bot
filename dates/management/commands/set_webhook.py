from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from dates import telegram as tg

COMMANDS = [
    ("app", "Відкрити застосунок"),
    ("idea", "Три ідеї на вихідні"),
    ("invite", "Запросити половинку"),
    ("remind", "Нагадування в четвер"),
    ("leave", "Вийти з пари"),
]


class Command(BaseCommand):
    help = "Реєструє webhook, команди і кнопку меню в Telegram"

    def handle(self, *args, **options):
        if not (settings.TELEGRAM_BOT_TOKEN and settings.PUBLIC_URL and settings.WEBHOOK_SECRET):
            raise CommandError("Заповни TELEGRAM_BOT_TOKEN, PUBLIC_URL і WEBHOOK_SECRET у .env")
        result = tg.api(
            "setWebhook",
            url=f"{settings.PUBLIC_URL}/tg/webhook/",
            secret_token=settings.WEBHOOK_SECRET,
            allowed_updates=["message"],
            drop_pending_updates=True,
        )
        if not result or not result.get("ok"):
            raise CommandError(f"Telegram відмовив: {result}")
        tg.api("setMyCommands", commands=[{"command": c, "description": d} for c, d in COMMANDS])
        tg.api(
            "setChatMenuButton",
            menu_button={"type": "web_app", "text": "Куди підемо?", "web_app": {"url": f"{settings.PUBLIC_URL}/app/"}},
        )
        self.stdout.write(self.style.SUCCESS(f"Webhook встановлено на {settings.PUBLIC_URL}/tg/webhook/"))
