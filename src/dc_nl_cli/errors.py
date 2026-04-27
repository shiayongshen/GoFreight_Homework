class DCNLError(Exception):
    """Base exception for the CLI."""


class ConfigurationError(DCNLError):
    """Raised when required configuration is missing or invalid."""


class ParseError(DCNLError):
    """Raised when the query cannot be parsed into the canonical schema."""


class ResolutionError(DCNLError):
    """Raised when place or stat var resolution fails."""


class ExecutionError(DCNLError):
    """Raised when the downstream query execution fails."""
