"""Data lake ingestion pipeline with purpose limitation enforcement."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime

from src.common.dataclassification import ClassificationRegistry


class DestinationDeniedError(Exception):
    """Raised when data lake write is denied due to destination policy."""


@dataclass
class IngestionManifest:
    """Manifest for data lake ingestion with purpose metadata."""
    purpose: str
    data_class: str
    owner: str
    destination: str
    approved_destinations: List[str]
    records: List[Dict[str, Any]]
    timestamp: str = ""


@dataclass
class AuditEntry:
    """Audit entry for a data lake write — no record content."""
    timestamp: str
    purpose: str
    data_class: str
    owner: str
    destination: str
    record_count: int
    source: str = "ingestion_pipeline"


class DataLakeWriter:
    """Data lake ingestion writer with purpose limitation enforcement."""

    def __init__(self, registry: Optional[ClassificationRegistry] = None):
        self._registry = registry or ClassificationRegistry()
        self._audit: List[AuditEntry] = []
        self._storage: Dict[str, List[Dict[str, Any]]] = {}

    def write(self, manifest: IngestionManifest) -> bool:
        """Write a manifest to the data lake after destination validation."""
        # Validate required fields
        if not manifest.purpose:
            raise ValueError("IngestionManifest must have a purpose")
        if not manifest.data_class:
            raise ValueError("IngestionManifest must have a data_class")
        if not manifest.owner:
            raise ValueError("IngestionManifest must have an owner")
        if not manifest.destination:
            raise ValueError("IngestionManifest must have a destination")

        # Validate destination against classification registry
        try:
            allowed = self._registry.validate_destination(manifest.data_class, manifest.destination)
        except Exception as e:
            raise DestinationDeniedError(f"Classification validation failed: {e}")

        if not allowed:
            # Also check inline approved_destinations as fallback
            if manifest.approved_destinations and manifest.destination not in manifest.approved_destinations:
                raise DestinationDeniedError(
                    f"Destination '{manifest.destination}' is not approved for "
                    f"data class '{manifest.data_class}' (approved: {manifest.approved_destinations})"
                )

        # Write records
        if manifest.destination not in self._storage:
            self._storage[manifest.destination] = []
        self._storage[manifest.destination].extend(manifest.records)

        # Create audit entry (metadata only — NO record content)
        entry = AuditEntry(
            timestamp=manifest.timestamp or datetime.utcnow().isoformat(),
            purpose=manifest.purpose,
            data_class=manifest.data_class,
            owner=manifest.owner,
            destination=manifest.destination,
            record_count=len(manifest.records),
        )
        self._audit.append(entry)
        return True

    def get_audit_report(self) -> List[Dict[str, Any]]:
        """Return audit entries — metadata only, no record content."""
        return [
            {
                "timestamp": e.timestamp,
                "purpose": e.purpose,
                "data_class": e.data_class,
                "owner": e.owner,
                "destination": e.destination,
                "record_count": e.record_count,
                "source": e.source,
            }
            for e in self._audit
        ]

    def get_writes_by_purpose(self, purpose: str) -> List[Dict[str, Any]]:
        """Filter audit entries by purpose."""
        return [
            e for e in self.get_audit_report()
            if e["purpose"] == purpose
        ]

    def get_writes_by_owner(self, owner: str) -> List[Dict[str, Any]]:
        """Filter audit entries by owner."""
        return [
            e for e in self.get_audit_report()
            if e["owner"] == owner
        ]
