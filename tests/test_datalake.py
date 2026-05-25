"""Tests for data lake purpose limitation enforcement."""
import pytest
from src.common.datalake import DataLakeWriter, IngestionManifest, DestinationDeniedError, AuditEntry
from src.common.dataclassification import (
    ClassificationRegistry, DataClass, DataPurpose, ClassificationError,
)


class TestClassificationRegistry:
    def test_register_and_validate(self):
        registry = ClassificationRegistry()
        purpose = DataPurpose(
            name="analytics",
            description="Internal analytics",
            allowed_destinations={"analytics_warehouse", "dashboard"},
        )
        registry.register_data_class("task_metrics", DataClass.INTERNAL, "data-team", [purpose])

        assert registry.validate_destination("task_metrics", "analytics_warehouse") is True
        assert registry.validate_destination("task_metrics", "dashboard") is True

    def test_deny_unapproved_destination(self):
        registry = ClassificationRegistry()
        purpose = DataPurpose(
            name="analytics",
            description="Internal analytics",
            allowed_destinations={"analytics_warehouse"},
        )
        registry.register_data_class("task_metrics", DataClass.INTERNAL, "data-team", [purpose])

        assert registry.validate_destination("task_metrics", "public_bucket") is False

    def test_unknown_class_raises_error(self):
        registry = ClassificationRegistry()
        with pytest.raises(ClassificationError):
            registry.validate_destination("nonexistent", "any_dest")

    def test_list_registrations(self):
        registry = ClassificationRegistry()
        purpose = DataPurpose(name="ops", description="Operations", allowed_destinations={"ops_db"})
        registry.register_data_class("ops_logs", DataClass.CONFIDENTIAL, "ops-team", [purpose])
        registrations = registry.list_registrations()
        assert len(registrations) == 1
        assert registrations[0].name == "ops_logs"

    def test_get_allowed_destinations(self):
        registry = ClassificationRegistry()
        p1 = DataPurpose(name="analytics", description="Analytics", allowed_destinations={"warehouse", "dashboard"})
        p2 = DataPurpose(name="backup", description="Backup", allowed_destinations={"cold_storage"})
        registry.register_data_class("user_data", DataClass.CONFIDENTIAL, "sec-team", [p1, p2])
        destinations = registry.get_allowed_destinations("user_data")
        assert "warehouse" in destinations
        assert "dashboard" in destinations
        assert "cold_storage" in destinations


class TestDataLakeWriter:
    def test_write_requires_purpose(self):
        writer = DataLakeWriter()
        manifest = IngestionManifest(
            purpose="", data_class="internal", owner="alice",
            destination="warehouse", approved_destinations=[],
            records=[{"id": 1}],
        )
        with pytest.raises(ValueError):
            writer.write(manifest)

    def test_write_requires_data_class(self):
        writer = DataLakeWriter()
        manifest = IngestionManifest(
            purpose="analytics", data_class="", owner="alice",
            destination="warehouse", approved_destinations=[],
            records=[{"id": 1}],
        )
        with pytest.raises(ValueError):
            writer.write(manifest)

    def test_write_requires_owner(self):
        writer = DataLakeWriter()
        manifest = IngestionManifest(
            purpose="analytics", data_class="internal", owner="",
            destination="warehouse", approved_destinations=[],
            records=[{"id": 1}],
        )
        with pytest.raises(ValueError):
            writer.write(manifest)

    def test_write_requires_destination(self):
        writer = DataLakeWriter()
        manifest = IngestionManifest(
            purpose="analytics", data_class="internal", owner="alice",
            destination="", approved_destinations=[],
            records=[{"id": 1}],
        )
        with pytest.raises(ValueError):
            writer.write(manifest)

    def test_approved_destination_succeeds(self):
        writer = DataLakeWriter()
        # Pre-register data class with allowed destination
        writer._registry.register_data_class(
            "task_metrics", DataClass.INTERNAL, "data-team",
            [DataPurpose(name="analytics", description="Analytics", allowed_destinations={"analytics_warehouse"})],
        )
        manifest = IngestionManifest(
            purpose="analytics", data_class="task_metrics", owner="alice",
            destination="analytics_warehouse", approved_destinations=["analytics_warehouse"],
            records=[{"task_id": 1, "duration": 30}],
        )
        assert writer.write(manifest) is True

    def test_unapproved_destination_fails(self):
        writer = DataLakeWriter()
        writer._registry.register_data_class(
            "task_metrics", DataClass.INTERNAL, "data-team",
            [DataPurpose(name="analytics", description="Analytics", allowed_destinations={"analytics_warehouse"})],
        )
        manifest = IngestionManifest(
            purpose="analytics", data_class="task_metrics", owner="alice",
            destination="public_bucket", approved_destinations=["analytics_warehouse"],
            records=[{"task_id": 1}],
        )
        with pytest.raises(DestinationDeniedError):
            writer.write(manifest)

    def test_audit_report_has_metadata_no_content(self):
        writer = DataLakeWriter()
        writer._registry.register_data_class(
            "task_metrics", DataClass.INTERNAL, "data-team",
            [DataPurpose(name="analytics", description="Analytics", allowed_destinations={"warehouse"})],
        )
        manifest = IngestionManifest(
            purpose="analytics", data_class="task_metrics", owner="alice",
            destination="warehouse", approved_destinations=["warehouse"],
            records=[{"task_id": 1, "duration": 30, "user_email": "test@example.com"}],
        )
        writer.write(manifest)

        report = writer.get_audit_report()
        assert len(report) == 1
        entry = report[0]
        # Has metadata
        assert entry["purpose"] == "analytics"
        assert entry["data_class"] == "task_metrics"
        assert entry["owner"] == "alice"
        assert entry["destination"] == "warehouse"
        assert entry["record_count"] == 1
        # Does NOT expose record content
        assert "records" not in entry
        assert "task_id" not in str(entry)
        assert "user_email" not in str(entry)
        assert "duration" not in str(entry)

    def test_filter_by_purpose(self):
        writer = DataLakeWriter()
        writer._registry.register_data_class("logs", DataClass.INTERNAL, "team",
            [DataPurpose(name="analytics", allowed_destinations={"lake"}, description="")])
        writer.write(IngestionManifest(purpose="analytics", data_class="logs", owner="bob",
            destination="lake", approved_destinations=["lake"], records=[{"x": 1}]))
        writer.write(IngestionManifest(purpose="analytics", data_class="logs", owner="alice",
            destination="lake", approved_destinations=["lake"], records=[{"x": 2}]))
        writer.write(IngestionManifest(purpose="backup", data_class="logs", owner="bob",
            destination="lake", approved_destinations=["lake"], records=[{"x": 3}]))
        analytics_writes = writer.get_writes_by_purpose("analytics")
        assert len(analytics_writes) == 2
        backup_writes = writer.get_writes_by_purpose("backup")
        assert len(backup_writes) == 1
