"""
Direct debit charging runner.

Selects approved, active mandates whose next payment is due and charges each via Hubtel.
Kept separate from the Celery task so it is unit-testable and reusable by a management command.
"""
import logging

from django.utils import timezone

from subscriptions.models import DirectDebit
from subscriptions.services.hubtel_service import HubtelPaymentService

logger = logging.getLogger(__name__)


def charge_due_direct_debits():
    """
    Charge every approved, active mandate whose next_payment_date is due.

    One mandate's failure never aborts the batch. ValueError covers expected guard/validation
    skips (in-flight charge, fully paid, inactive wallet); other exceptions are logged as
    failures and retried on the next run.

    Returns:
        dict summary: {'due', 'charged', 'skipped', 'failed'}
    """
    today = timezone.localdate()
    due = DirectDebit.objects.filter(
        approval_status=True,
        is_active=True,
        next_payment_date__lte=today,
    )

    service = HubtelPaymentService()
    charged = skipped = failed = 0
    for direct_debit in due.iterator():
        try:
            service.charge_direct_debit(direct_debit)
            charged += 1
        except ValueError as e:
            skipped += 1
            logger.info("Skipped direct debit %s: %s", direct_debit.id, e)
        except Exception as e:
            failed += 1
            logger.warning("Failed to charge direct debit %s: %s", direct_debit.id, e)

    summary = {
        'due': charged + skipped + failed,
        'charged': charged,
        'skipped': skipped,
        'failed': failed,
    }
    logger.info("Direct debit run complete: %s", summary)
    return summary
