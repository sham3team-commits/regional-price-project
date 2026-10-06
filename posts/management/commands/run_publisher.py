import asyncio

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from posts import worker


class Command(BaseCommand):
    help = "Run the Telegram publisher worker (scheduled posts and comment control)."

    def handle(self, *args, **options):
        if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHANNEL_ID:
            raise CommandError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID must be set.")
        asyncio.run(worker.main())
