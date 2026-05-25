"""Tests for analytics anonymization validator."""
import pytest
from src.common.analytics import (
    AnonymizationValidator, AnonymizationError, MetricsAggregator,
    SuppressedGroupInfo,
)


class TestAnonymizationValidator:
    """Test suite for AnonymizationValidator."""

    def test_small_groups_blocked(self):
        """Groups below threshold raise AnonymizationError."""
        validator = AnonymizationValidator(minimum_threshold=5)
        groups = {"team_a": 3, "team_b": 2}
        with pytest.raises(AnonymizationError, match=".*5.*"):
            validator.validate_anonymization(groups)

    def test_large_groups_pass(self):
        """Large groups pass through."""
        validator = AnonymizationValidator(minimum_threshold=5)
        groups = {"team_c": 50, "team_d": 200}
        result = validator.validate_anonymization(groups)
        assert result == {"team_c": 50, "team_d": 200}

    def test_mixed_groups_filtered(self):
        """Only small groups removed, large groups stay."""
        validator = AnonymizationValidator(minimum_threshold=5)
        groups = {"small": 2, "medium": 5, "big": 100}
        result = validator.validate_anonymization(groups)
        assert "small" not in result
        assert result["medium"] == 5
        assert result["big"] == 100

    def test_boundary_exact_threshold(self):
        """Group exactly at threshold passes."""
        validator = AnonymizationValidator(minimum_threshold=5)
        groups = {"boundary": 5}
        result = validator.validate_anonymization(groups)
        assert result["boundary"] == 5

    def test_suppressed_no_content_leak(self):
        """Suppressed groups report metadata only, no record content."""
        validator = AnonymizationValidator(minimum_threshold=5)
        groups = {"small_team": 1}
        with pytest.raises(AnonymizationError):
            validator.validate_anonymization(groups)
        suppressed = validator.suppressed_groups
        assert len(suppressed) == 1
        info = suppressed[0]
        assert info["group_key"] == "small_team"
        assert info["reason"] is not None
        assert "content" not in info
        assert "records" not in info
        assert "data" not in info

    def test_custom_threshold(self):
        """Custom threshold works."""
        validator = AnonymizationValidator(minimum_threshold=10)
        groups = {"group_a": 9, "group_b": 10}
        result = validator.validate_anonymization(groups)
        assert "group_a" not in result
        assert result["group_b"] == 10

    def test_reset_clears_suppressed(self):
        """Reset clears suppressed tracking."""
        validator = AnonymizationValidator(minimum_threshold=5)
        with pytest.raises(AnonymizationError):
            validator.validate_anonymization({"x": 1})
        assert len(validator.suppressed_groups) == 1
        validator.reset()
        assert len(validator.suppressed_groups) == 0

    def test_invalid_threshold(self):
        """Threshold must be >= 1."""
        with pytest.raises(ValueError):
            AnonymizationValidator(minimum_threshold=0)

    def test_suppress_group_manual(self):
        """Manual suppression adds metadata without content."""
        validator = AnonymizationValidator(minimum_threshold=5)
        validator.suppress_group("manual_group", {"sensitive": "data"})
        suppressed = validator.suppressed_groups
        assert len(suppressed) == 1
        info = suppressed[0]
        assert info["group_key"] == "manual_group"
        assert "sensitive" not in str(info)
        assert "data" not in str(info.get("reason", ""))


class TestMetricsAggregator:
    """Integration tests for MetricsAggregator with AnonymizationValidator."""

    def test_aggregator_all_passes(self):
        """Records collected and published with valid groups."""
        agg = MetricsAggregator(minimum_threshold=2)
        agg.add_record("users", {"id": 1})
        agg.add_record("users", {"id": 2})
        agg.add_record("users", {"id": 3})
        result = agg.publish()
        assert result["users"] == 3

    def test_aggregator_small_group_fails(self):
        """Small groups cause publish failure."""
        agg = MetricsAggregator(minimum_threshold=5)
        agg.add_record("users", {"id": 1})
        agg.add_record("users", {"id": 2})
        with pytest.raises(AnonymizationError):
            agg.publish()

    def test_aggregator_custom_threshold(self):
        """Custom threshold passes through publish."""
        agg = MetricsAggregator(minimum_threshold=3)
        agg.add_record("team", {"id": 1})
        agg.add_record("team", {"id": 2})
        agg.add_record("team", {"id": 3})
        result = agg.publish()
        assert result["team"] == 3

    def test_aggregator_suppressed_no_leak(self):
        """Suppressed groups in aggregator tracked with metadata only."""
        agg = MetricsAggregator(minimum_threshold=5)
        agg.add_record("tiny", {"secret": "password"})
        with pytest.raises(AnonymizationError):
            agg.publish()
        suppressed = agg.validator.suppressed_groups
        assert len(suppressed) == 1
        info = suppressed[0]
        assert info["group_key"] == "tiny"
        assert "secret" not in str(info)
        assert "password" not in str(info)
