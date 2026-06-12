from choirbackend.celery import app
from subscriptions.services.direct_debit_runner import charge_due_direct_debits as _run_due_charges


@app.task
def send_email():
    print("Sending email")


@app.task(name='subscriptions.tasks.charge_due_direct_debits')
def charge_due_direct_debits():
    """Daily beat task: charge all direct-debit mandates that are due today."""
    return _run_due_charges()