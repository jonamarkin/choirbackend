from django.core.management.base import BaseCommand

from subscriptions.services.direct_debit_runner import charge_due_direct_debits


class Command(BaseCommand):
    help = "Charge all approved, active direct-debit mandates whose next payment is due."

    def handle(self, *args, **options):
        summary = charge_due_direct_debits()
        self.stdout.write(self.style.SUCCESS(f"Direct debit run: {summary}"))
