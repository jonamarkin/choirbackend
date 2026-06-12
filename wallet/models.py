import uuid

from django.db import models
from django.utils import timezone

from authentication.models import User
from wallet.utils.wallet_network_type import WalletNetworkType


class MobileWallet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, null=False, blank=False)
    description = models.TextField(
        null=True,
        blank=True,
        help_text="Optional description of the wallet"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wallets')
    network = models.CharField(choices=WalletNetworkType.choices(), max_length=20, null=False, blank=False)
    account_number = models.CharField(max_length=20, null=False, blank=False, unique=True)
    is_active = models.BooleanField(default=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mobile_wallets'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['account_number']),
        ]
        unique_together = [['user', 'account_number']]

    def mark_verified(self):
        self.verified_at = timezone.now()
        self.is_active = True
        self.save(update_fields=['verified_at', 'is_active', 'updated_at'])
