"""Infera custom exceptions."""


class InferaError(Exception):
    """Base exception for all Infera errors."""

    pass


class ConfigurationError(InferaError):
    """Error in configuration."""

    pass


class PreflightError(InferaError):
    """Error during preflight checks."""

    pass


class DeploymentError(InferaError):
    """Error during deployment."""

    pass
