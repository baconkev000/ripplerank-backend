"""
Remove AgentActivityLog records older than 30 days.

Keeps the last 30 days of history (including the current day). Run daily via cron, e.g.:
  0 2 * * * cd /path/to/backend && python manage.py cleanup_old_agent_activity
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import AgentActivityLog


class Command(BaseCommand):
    help = "Delete agent activity log entries older than 30 days (keeps last 30 days including today)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report how many rows would be deleted.",
        )

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=30)
        qs = AgentActivityLog.objects.filter(created_at__lt=cutoff)
        count = qs.count()

        if options["dry_run"]:
            self.stdout.write(f"Would delete {count} agent activity log(s) older than {cutoff.isoformat()}.")
            return

        qs.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} agent activity log(s) older than 30 days."))
