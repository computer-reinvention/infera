"""Infera custom exceptions."""


class InferaError(Exception):
    """Base exception for all Infera errors."""

    pass


class ConfigurationError(InferaError):
    """Error in configuration."""

    pass


class ProvisionError(InferaError):
    """Error during resource provisioning."""

    def __init__(self, message: str, resource_id: str | None = None):
        super().__init__(message)
        self.resource_id = resource_id


class AuthenticationError(InferaError):
    """Error during cloud provider authentication."""

    pass


class AnalysisError(InferaError):
    """Error during codebase analysis."""

    pass


class RollbackError(InferaError):
    """Error during rollback after a failed provisioning."""

    def __init__(self, message: str, partial_resources: list[str] | None = None):
        super().__init__(message)
        self.partial_resources = partial_resources or []
