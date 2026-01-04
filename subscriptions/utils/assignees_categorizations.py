from enum import Enum


class AssigneesCategorizations(Enum):
    EXECUTIVES = 'EXECUTIVES'
    MEMBERS = 'MEMBERS'
    BOTH = 'BOTH'

    @classmethod
    def choices(cls):
        return [(category.value, category.value) for category in cls]

    @staticmethod
    def from_string(category: str):
        """
        Parses a string to match and return a corresponding AssigneesCategorizations
        category based on its name or value.

        Args:
            category (str): The name or value of the assignees category to match.

        Returns:
            AssigneesCategorizations: The matching category.

        Raises:
            ValueError: If no matching category is found for the given string.
        """
        for category in AssigneesCategorizations:
            if category.name == category or category.value == category:
                return category
        raise ValueError(f"Invalid assignees category: {category}")
