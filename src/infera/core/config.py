"""Infera configuration models."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ResourceSpec(BaseModel):
    """Specification for a cloud resource."""

    id: str = Field(description="Unique identifier for this resource")
    type: str = Field(description="Resource type (cloud_run, cloud_storage, etc.)")
    name: str = Field(description="Resource name in cloud provider")
    provider: str = Field(description="Cloud provider (gcp, aws, azure)")
    config: dict[str, Any] = Field(
        default_factory=dict, description="Provider-specific config"
    )
    depends_on: list[str] = Field(
        default_factory=list, description="Resource IDs this depends on"
    )


class DomainConfig(BaseModel):
    """Custom domain configuration."""

    enabled: bool = False
    name: str | None = None
    ssl: bool = True
    dns_provider: str | None = None


class InferaConfig(BaseModel):
    """Main Infera project configuration."""

    version: str = "1.0"
    project_name: str
    provider: Literal["gcp", "aws", "azure", "cloudflare"]
    region: str | None = None  # Region (not used for Cloudflare - global edge)
    project_id: str | None = (
        None  # Cloud provider project ID (GCP), account_id (Cloudflare)
    )

    # Detected from codebase
    detected_frameworks: list[dict] = Field(default_factory=list[dict])
    has_dockerfile: bool = False
    entry_point: str | None = None

    # Architecture
    architecture_type: str | None = (
        None  # static_site, api_service, fullstack_app, etc.
    )
    resources: list[ResourceSpec] = Field(default_factory=list)

    # Optional
    domain: DomainConfig | None = None

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def get_resource(self, resource_id: str) -> ResourceSpec | None:
        """Get resource by ID."""
        for resource in self.resources:
            if resource.id == resource_id:
                return resource
        return None
