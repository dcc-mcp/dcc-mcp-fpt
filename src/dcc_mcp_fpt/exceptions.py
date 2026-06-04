"""ShotGrid-specific exceptions for dcc-mcp-fpt."""


class ShotGridError(Exception):
    """Base exception for all ShotGrid adapter errors."""


class ShotGridConnectionError(ShotGridError):
    """Raised when unable to connect to the ShotGrid API."""


class ShotGridAuthenticationError(ShotGridError):
    """Raised when authentication to ShotGrid fails."""


class ShotGridValidationError(ShotGridError):
    """Raised when entity data fails schema validation."""


class ShotGridEntityNotFoundError(ShotGridError):
    """Raised when a requested entity does not exist."""


class ShotGridQueryError(ShotGridError):
    """Raised when a ShotGrid query fails or is malformed."""


class ShotGridSchemaError(ShotGridError):
    """Raised when schema loading or caching fails."""
