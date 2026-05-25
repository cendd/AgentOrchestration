"""Analytics anonymization validator for data warehouse publish."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Any


class AnonymizationError(Exception):
    """Raised when a group fails anonymization threshold check."""


@dataclass
class SuppressedGroupInfo:
    """Metadata-only summary of a suppressed group — no content leak."""
    group_key: str
    reason: str
    threshold: int
    actual_size: int


class AnonymizationValidator:
    """Validates that metric groups meet anonymity thresholds before publishing."""

    def __init__(self, minimum_threshold: int = 5):
        if minimum_threshold < 1:
            raise ValueError("minimum_threshold must be >= 1")
        self.minimum_threshold = minimum_threshold
        self._suppressed: List[SuppressedGroupInfo] = []

    def check_minimum_group_size(self, group_size: int) -> bool:
        """Check if a group meets the minimum size threshold."""
        return group_size >= self.minimum_threshold

    def validate_anonymization(self, groups: Dict[str, int]) -> Dict[str, int]:
        """Validate all groups. Returns groups that pass threshold, raises if none pass."""
        passed: Dict[str, int] = {}
        for key, size in groups.items():
            if self.check_minimum_group_size(size):
                passed[key] = size
            else:
                self._suppressed.append(SuppressedGroupInfo(
                    group_key=key,
                    reason=f"Group size {size} below minimum threshold {self.minimum_threshold}",
                    threshold=self.minimum_threshold,
                    actual_size=size,
                ))
        if not passed:
            raise AnonymizationError(
                f"All {len(groups)} groups failed anonymization check (threshold={self.minimum_threshold})"
            )
        return passed

    def suppress_group(self, group_key: str, group_data: Any) -> None:
        """Manually suppress a single group — only metadata tracked, no content stored."""
        self._suppressed.append(SuppressedGroupInfo(
            group_key=group_key,
            reason="Manually suppressed",
            threshold=self.minimum_threshold,
            actual_size=0,
        ))

    @property
    def suppressed_groups(self) -> List[Dict[str, Any]]:
        """Return metadata-only summaries with NO content or record data."""
        return [
            {"group_key": info.group_key, "reason": info.reason,
             "threshold": info.threshold, "actual_size": info.actual_size}
            for info in self._suppressed
        ]

    def reset(self) -> None:
        """Clear all suppressed group tracking."""
        self._suppressed.clear()


@dataclass
class MetricsAggregator:
    """Collects metrics with built-in anonymization validation."""
    validator: AnonymizationValidator = field(default_factory=AnonymizationValidator)
    _groups: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    def add_record(self, group_key: str, record: Dict[str, Any]) -> None:
        if group_key not in self._groups:
            self._groups[group_key] = []
        self._groups[group_key].append(record)

    def publish(self, threshold: Optional[int] = None) -> Dict[str, int]:
        """Validate and return group sizes. Raises AnonymizationError if threshold not met."""
        if threshold is not None:
            self.validator.minimum_threshold = threshold
        group_sizes = {k: len(v) for k, v in self._groups.items()}
        return self.validator.validate_anonymization(group_sizes)
