"""Static cab parsing and formatting errors."""


class CabLoadError(ValueError):
    """A cab document could not be parsed or compiled."""


class UnsupportedFlavourError(ValueError):
    """Only binary commands can be formatted as executable argv."""
