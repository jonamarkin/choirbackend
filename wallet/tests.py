from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from authentication.models import OTP
from core.models import Organization
from wallet.models import MobileWallet

User = get_user_model()


class WalletAPITests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name='Wallet Org',
            slug='wallet-org',
            contact_email='wallet@example.com',
            contact_phone='0200000000',
            code='4821',
        )
        self.user = User.objects.create_user(
            username='walletuser',
            email='walletuser@example.com',
            password='password123',
            organization=self.organization,
            role='member',
            is_active=True,
        )
        self.other_user = User.objects.create_user(
            username='otherwalletuser',
            email='otherwalletuser@example.com',
            password='password123',
            organization=self.organization,
            role='member',
            is_active=True,
        )
        self.client.force_authenticate(self.user)

    def wallet_payload(self, **overrides):
        payload = {
            'name': 'Main Wallet',
            'description': 'Primary wallet',
            'network': 'MTN',
            'account_number': '020 123 4567',
        }
        payload.update(overrides)
        return payload

    @patch('authentication.services.SMSService.send_sms', return_value=True)
    def test_request_otp_sends_sms_for_new_wallet(self, mock_send_sms):
        response = self.client.post('/api/v1/wallets/request-otp', self.wallet_payload(), format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'OTP sent successfully.')
        mock_send_sms.assert_called_once()
        self.assertTrue(
            OTP.objects.filter(target='233201234567', purpose='wallet_verification').exists()
        )
        self.assertFalse(MobileWallet.objects.exists())

    @patch('authentication.services.SMSService.send_sms', return_value=True)
    def test_verify_create_creates_wallet_after_valid_otp(self, _mock_send_sms):
        self.client.post('/api/v1/wallets/request-otp', self.wallet_payload(), format='json')
        otp = OTP.objects.filter(target='233201234567', purpose='wallet_verification').latest('created_at')

        response = self.client.post(
            '/api/v1/wallets/verify-create',
            self.wallet_payload(otp_code=otp.code),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(MobileWallet.objects.count(), 1)
        wallet = MobileWallet.objects.get()
        self.assertEqual(wallet.user, self.user)
        self.assertEqual(wallet.account_number, '233201234567')
        self.assertTrue(wallet.is_active)
        self.assertIsNotNone(wallet.verified_at)

    @patch('authentication.services.SMSService.send_sms', return_value=True)
    def test_verify_create_rejects_invalid_otp(self, _mock_send_sms):
        response = self.client.post(
            '/api/v1/wallets/verify-create',
            self.wallet_payload(otp_code='000000'),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(MobileWallet.objects.count(), 0)

    def test_request_otp_rejects_duplicate_account_number_globally(self):
        MobileWallet.objects.create(
            user=self.other_user,
            name='Existing',
            description='',
            network='MTN',
            account_number='233201234567',
            is_active=True,
        )

        response = self.client.post('/api/v1/wallets/request-otp', self.wallet_payload(), format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('account_number', response.data)

    def test_direct_create_endpoint_is_disabled(self):
        response = self.client.post('/api/v1/wallets/', self.wallet_payload(), format='json')

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_list_returns_only_current_users_wallets(self):
        own_wallet = MobileWallet.objects.create(
            user=self.user,
            name='Own',
            description='',
            network='MTN',
            account_number='233201234567',
            is_active=True,
        )
        MobileWallet.objects.create(
            user=self.other_user,
            name='Other',
            description='',
            network='TELECEL',
            account_number='233271234567',
            is_active=True,
        )

        response = self.client.get('/api/v1/wallets/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], str(own_wallet.id))

    def test_patch_allows_renaming_only(self):
        wallet = MobileWallet.objects.create(
            user=self.user,
            name='Old Name',
            description='Old description',
            network='MTN',
            account_number='233201234567',
            is_active=True,
        )

        response = self.client.patch(
            f'/api/v1/wallets/{wallet.id}',
            {'name': 'New Name'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        wallet.refresh_from_db()
        self.assertEqual(wallet.name, 'New Name')
        self.assertEqual(wallet.account_number, '233201234567')

    def test_patch_rejects_account_number_change(self):
        wallet = MobileWallet.objects.create(
            user=self.user,
            name='Wallet',
            description='',
            network='MTN',
            account_number='233201234567',
            is_active=True,
        )

        response = self.client.patch(
            f'/api/v1/wallets/{wallet.id}',
            {'account_number': '0209999999'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        wallet.refresh_from_db()
        self.assertEqual(wallet.account_number, '233201234567')

    @patch('authentication.services.SMSService.send_sms', return_value=False)
    def test_request_otp_fails_when_sms_delivery_fails(self, _mock_send_sms):
        response = self.client.post('/api/v1/wallets/request-otp', self.wallet_payload(), format='json')

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(OTP.objects.count(), 0)

    def test_deactivate_marks_wallet_inactive(self):
        wallet = MobileWallet.objects.create(
            user=self.user,
            name='Wallet',
            description='',
            network='MTN',
            account_number='233201234567',
            is_active=True,
        )

        response = self.client.post(f'/api/v1/wallets/{wallet.id}/deactivate')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        wallet.refresh_from_db()
        self.assertFalse(wallet.is_active)

    @patch('authentication.services.SMSService.send_sms', return_value=True)
    def test_reactivate_requires_valid_otp(self, _mock_send_sms):
        wallet = MobileWallet.objects.create(
            user=self.user,
            name='Wallet',
            description='',
            network='MTN',
            account_number='233201234567',
            is_active=False,
        )

        otp_response = self.client.post(f'/api/v1/wallets/{wallet.id}/request-reactivation-otp')
        self.assertEqual(otp_response.status_code, status.HTTP_200_OK)

        otp = OTP.objects.filter(target='233201234567', purpose='wallet_verification').latest('created_at')
        verify_response = self.client.post(
            f'/api/v1/wallets/{wallet.id}/verify-reactivate',
            {'otp_code': otp.code},
            format='json',
        )

        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)
        wallet.refresh_from_db()
        self.assertTrue(wallet.is_active)
        self.assertIsNotNone(wallet.verified_at)

    def test_cannot_access_another_users_wallet(self):
        wallet = MobileWallet.objects.create(
            user=self.other_user,
            name='Other Wallet',
            description='',
            network='MTN',
            account_number='233201234567',
            is_active=True,
        )

        response = self.client.post(f'/api/v1/wallets/{wallet.id}/deactivate')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
