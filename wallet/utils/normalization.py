from rest_framework import serializers


def normalize_wallet_account_number(account_number: str) -> str:
    raw_value = str(account_number or '').strip()
    digits = ''.join(char for char in raw_value if char.isdigit())

    if not digits:
        raise serializers.ValidationError('Wallet number is required.')

    if digits.startswith('233') and len(digits) == 12:
        normalized = digits
    elif digits.startswith('0') and len(digits) == 10:
        normalized = f"233{digits[1:]}"
    elif len(digits) == 9:
        normalized = f"233{digits}"
    else:
        raise serializers.ValidationError(
            'Wallet number must be a valid Ghana mobile money number.'
        )

    return normalized
