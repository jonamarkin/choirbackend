import calendar
from datetime import date, timedelta
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

    @staticmethod
    def _add_months(base, months):
        """Add `months` to `base`, clamping the day to the target month's length."""
        month_index = base.month - 1 + months
        year = base.year + month_index // 12
        month = month_index % 12 + 1
        day = min(base.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)

    @staticmethod
    def next_date(period_value, from_date=None):
        """
        Compute the next payment date for a given period type.

        Args:
            period_value (str): One of the AutoDebitPeriodTypes values.
            from_date (date): Base date to count from (defaults to today).

        Returns:
            date: The next scheduled date.

        Raises:
            ValueError: If `period_value` is not a recognised period type.
        """
        base = from_date or date.today()
        if period_value == AutoDebitPeriodTypes.DAILY.value:
            return base + timedelta(days=1)
        if period_value == AutoDebitPeriodTypes.WEEKLY.value:
            return base + timedelta(weeks=1)

        months = {
            AutoDebitPeriodTypes.MONTHLY.value: 1,
            AutoDebitPeriodTypes.QUARTERLY.value: 3,
            AutoDebitPeriodTypes.ANNUALLY.value: 12,
        }.get(period_value)
        if months is None:
            raise ValueError(f"Invalid period type: {period_value}")
        return AutoDebitPeriodTypes._add_months(base, months)
