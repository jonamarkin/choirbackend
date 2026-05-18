from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from authentication.services import OTPService
from wallet.models import MobileWallet
from wallet.serializers import (
    ErrorResponseSerializer,
    MessageResponseSerializer,
    WalletOTPRequestSerializer,
    WalletSerializer,
    WalletUpdateSerializer,
    WalletVerifyCreateSerializer,
    WalletVerifyReactivationSerializer,
)


@extend_schema(tags=['Wallets'])
class MobileWalletViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = WalletSerializer

    def get_queryset(self):
        return MobileWallet.objects.filter(user=self.request.user).order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'request_otp':
            return WalletOTPRequestSerializer
        if self.action == 'verify_create':
            return WalletVerifyCreateSerializer
        if self.action in ['update', 'partial_update']:
            return WalletUpdateSerializer
        if self.action == 'verify_reactivate':
            return WalletVerifyReactivationSerializer
        return WalletSerializer

    @extend_schema(
        summary="Request wallet OTP",
        description=(
            "Validate the supplied wallet details and send a one-time passcode "
            "via SMS to the wallet's mobile money number. No wallet is created "
            "at this step — it is created once the OTP is verified."
        ),
        request=WalletOTPRequestSerializer,
        responses={
            200: MessageResponseSerializer,
            400: ErrorResponseSerializer,
            502: ErrorResponseSerializer,
        },
    )
    @action(detail=False, methods=['post'], url_path='request-otp')
    def request_otp(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            OTPService.generate_otp(
                target=serializer.validated_data['account_number'],
                purpose='wallet_verification',
                user=request.user,
                channel='sms',
                strict_delivery=True,
            )
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(
            {'message': 'OTP sent successfully.'},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Verify OTP & create wallet",
        description=(
            "Verify the OTP previously sent to the wallet's mobile money number "
            "and, on success, create the wallet (active and verified)."
        ),
        request=WalletVerifyCreateSerializer,
        responses={
            201: WalletSerializer,
            400: ErrorResponseSerializer,
        },
    )
    @action(detail=False, methods=['post'], url_path='verify-create')
    def verify_create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        wallet = serializer.create_wallet(request.user)
        return Response(WalletSerializer(wallet).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="List my wallets",
        description="List the authenticated user's mobile money wallets, newest first.",
        responses={200: WalletSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Get a wallet",
        description="Retrieve a single wallet owned by the authenticated user.",
        responses={200: WalletSerializer, 404: ErrorResponseSerializer},
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Replace wallet metadata",
        description=(
            "Replace the editable metadata (name, description) of a wallet. "
            "The account number and network are immutable."
        ),
        request=WalletUpdateSerializer,
        responses={200: WalletSerializer, 400: ErrorResponseSerializer},
    )
    def update(self, request, *args, **kwargs):
        wallet = self.get_object()
        serializer = self.get_serializer(wallet, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(WalletSerializer(wallet).data)

    @extend_schema(
        summary="Rename wallet",
        description=(
            "Partially update a wallet's metadata (name, description). "
            "The account number and network are immutable."
        ),
        request=WalletUpdateSerializer,
        responses={200: WalletSerializer, 400: ErrorResponseSerializer},
    )
    def partial_update(self, request, *args, **kwargs):
        wallet = self.get_object()
        serializer = self.get_serializer(wallet, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(WalletSerializer(wallet).data)

    @extend_schema(
        summary="Disabled — use the OTP flow",
        description=(
            "Direct creation is disabled. Create wallets via the "
            "`request-otp` then `verify-create` flow."
        ),
        responses={405: ErrorResponseSerializer},
    )
    def create(self, request, *args, **kwargs):
        return Response(
            {'error': 'Use the OTP verification flow to create wallets.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @extend_schema(
        summary="Disabled — deletion unsupported",
        description=(
            "Wallet deletion is not supported. Use `deactivate` to disable a wallet instead."
        ),
        responses={405: ErrorResponseSerializer},
    )
    def destroy(self, request, *args, **kwargs):
        return Response(
            {'error': 'Wallet deletion is not supported.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @extend_schema(
        summary="Deactivate wallet",
        description="Mark a wallet inactive. Reactivation later requires OTP verification.",
        responses={200: WalletSerializer, 400: ErrorResponseSerializer},
    )
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        wallet = self.get_object()
        if not wallet.is_active:
            return Response(
                {'error': 'Wallet is already inactive.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        wallet.is_active = False
        wallet.save(update_fields=['is_active', 'updated_at'])
        return Response(WalletSerializer(wallet).data)

    @extend_schema(
        summary="Request reactivation OTP",
        description=(
            "Send a one-time passcode via SMS to an inactive wallet's mobile money "
            "number so it can be reactivated."
        ),
        responses={
            200: MessageResponseSerializer,
            400: ErrorResponseSerializer,
            502: ErrorResponseSerializer,
        },
    )
    @action(detail=True, methods=['post'], url_path='request-reactivation-otp')
    def request_reactivation_otp(self, request, pk=None):
        wallet = self.get_object()
        if wallet.is_active:
            return Response(
                {'error': 'Wallet is already active.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            OTPService.generate_otp(
                target=wallet.account_number,
                purpose='wallet_verification',
                user=request.user,
                channel='sms',
                strict_delivery=True,
            )
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({'message': 'OTP sent successfully.'}, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Verify OTP & reactivate",
        description=(
            "Verify the reactivation OTP sent to the wallet's mobile money number "
            "and, on success, mark the wallet active and verified."
        ),
        request=WalletVerifyReactivationSerializer,
        responses={200: WalletSerializer, 400: ErrorResponseSerializer},
    )
    @action(detail=True, methods=['post'], url_path='verify-reactivate')
    def verify_reactivate(self, request, pk=None):
        wallet = self.get_object()
        if wallet.is_active:
            return Response(
                {'error': 'Wallet is already active.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        wallet = serializer.reactivate_wallet(wallet)
        return Response(WalletSerializer(wallet).data)
