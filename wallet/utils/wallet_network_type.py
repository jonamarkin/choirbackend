from enum import Enum


class WalletNetworkType(Enum):
    MTN = 'MTN'
    TELECEL = 'TELECEL'
    AIRTELTIGO = 'AIRTELTIGO'

    @classmethod
    def choices(cls):
        """
        Returns a list of tuples representing all possible choices in the enumeration.

        This method is typically used to generate choices for form fields or other
        structures that require tuple-based selection options.

        @return: A list of tuples with each tuple containing the enumeration value
        as both key and value
        @rtype: list[tuple[str, str]]
        """
        return [(network.value, network.value) for network in cls]

    @staticmethod
    def from_string(network_str):
        """
        Parses a string representation of a wallet network type and returns
        the corresponding WalletNetworkType enumeration instance. Supports
        lookup by both the enumeration's value and name. If the input string
        does not match any valid network type, a ValueError is raised.

        Args:
            network_str (str): String representation of the network type to parse.

        Returns:
            WalletNetworkType: The corresponding enumeration instance representing
            the wallet network type.

        Raises:
            ValueError: If `network_str` does not match any valid network type.
        """
        for network in WalletNetworkType:
            if network_str == network.value or network_str == network.name:
                return network
        raise ValueError(f"Invalid network type: {network_str}")
