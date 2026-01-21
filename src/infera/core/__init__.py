"""Core module - shared types, configuration, and state management."""

from infera.core.config import InferaConfig, ResourceSpec, DomainConfig
from infera.core.exceptions import InferaError, ConfigurationError
from infera.core.state import StateManager

__all__ = [
    "InferaConfig",
    "ResourceSpec",
    "DomainConfig",
    "StateManager",
    "InferaError",
    "ConfigurationError",
]
