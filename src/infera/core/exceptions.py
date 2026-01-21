"""Infera custom exceptions."""


class InferaError(Exception):
    """Base exception for all Infera errors."""

    pass


class ConfigurationError(InferaError):
    """Error in configuration."""

    pass
