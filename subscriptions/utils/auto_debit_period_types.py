from enum import Enum


class AutoDebitPeriodTypes(Enum):
    DAILY = 'DAILY'
    WEEKLY = 'WEEKLY'
    MONTHLY = 'MONTHLY'
    QUARTERLY = 'QUARTERLY'
    ANNUALLY = 'ANNUALLY'

    @classmethod
    def choices(cls):
        """
        Provides options for enumerations as a list of choices.

        Returns:
            List[Tuple[str, str]]: A list of tuples where each tuple contains
            the name and value of an enumeration member.
        """
        return [(period.value, period.value) for period in cls]

    @staticmethod
    def from_string(period_str):
        """
        Converts a string representation of an AutoDebitPeriodType into its corresponding
        enumeration value.

        This method attempts to match the input string with either the value or name of an
        existing enumeration type in the AutoDebitPeriodTypes enum.

        Args:
            period_str: str
                A string representing the period type. It can either match the value or name
                of an existing enumeration member.

        Returns:
            AutoDebitPeriodTypes
                The matching enumeration member corresponding to the input string.

        Raises:
            ValueError
                If the input string does not match any value or name in the enumeration.
        """
        for period_type in AutoDebitPeriodTypes:
            if period_type.value == period_str or period_type.name == period_str:
                return period_type
        raise ValueError(f"Invalid period type: {period_str}")
