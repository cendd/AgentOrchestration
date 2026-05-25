"""Data classification registry for purpose limitation enforcement."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set


class DataClass(Enum):
    """Data classification levels."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


@dataclass
class DataPurpose:
    """Declared purpose for data collection/processing."""
    name: str
    description: str
    allowed_destinations: Set[str]


@dataclass
class DataClassRegistration:
    """A registered data class with its allowed purposes."""
    name: str
    data_class: DataClass
    owner: str
    purposes: List[DataPurpose]


class ClassificationError(Exception):
    """Raised when classification validation fails."""


class ClassificationRegistry:
    """Registry for data classifications and their allowed purposes/destinations."""

    def __init__(self):
        self._registrations: Dict[str, DataClassRegistration] = {}

    def register_data_class(
        self, name: str, data_class: DataClass, owner: str, purposes: List[DataPurpose]
    ) -> DataClassRegistration:
        """Register a data class with its allowed purposes and destinations."""
        if not name:
            raise ClassificationError("Data class name must not be empty")
        if not purposes:
            raise ClassificationError("At least one purpose must be specified")

        registration = DataClassRegistration(
            name=name, data_class=data_class, owner=owner, purposes=purposes
        )
        self._registrations[name] = registration
        return registration

    def validate_destination(self, data_class_name: str, destination: str) -> bool:
        """Check if destination is approved for this data class."""
        registration = self._registrations.get(data_class_name)
        if not registration:
            raise ClassificationError(f"Unknown data class: {data_class_name}")

        for purpose in registration.purposes:
            if destination in purpose.allowed_destinations:
                return True
        return False

    def list_registrations(self) -> List[DataClassRegistration]:
        """List all registered data classes."""
        return list(self._registrations.values())

    def get_allowed_destinations(self, data_class_name: str) -> Set[str]:
        """Get all allowed destinations for a data class."""
        registration = self._registrations.get(data_class_name)
        if not registration:
            raise ClassificationError(f"Unknown data class: {data_class_name}")

        destinations: Set[str] = set()
        for purpose in registration.purposes:
            destinations.update(purpose.allowed_destinations)
        return destinations
