"""Tests for configuration management."""
import os
import pytest
from src.common.config import Config


class TestConfig:
    def test_get_existing_key(self):
        config = Config()
        config._data = {"db": {"host": "localhost", "port": 5432}}
        assert config.get("db.host") == "localhost"

    def test_get_nonexistent_key_returns_default(self):
        config = Config()
        assert config.get("nonexistent", "fallback") == "fallback"

    def test_set_nested_key(self):
        config = Config()
        config.set("logging.level", "debug")
        assert config._data["logging"]["level"] == "debug"

    def test_to_dict(self):
        config = Config()
        config._data = {"key": "value"}
        assert config.to_dict() == {"key": "value"}

    def test_env_override_only_known_keys(self):
        """Unrelated AO_ variables should NOT be loaded."""
        config = Config()
        config._data = {"db": {"host": "localhost"}}
        os.environ["AO_DB_HOST"] = "newhost"
        os.environ["AO_UNRELATED_VAR"] = "should_not_appear"
        config._load_env_overrides()
        # Known key is overridden
        assert config.get("db.host") == "newhost"
        # Unrelated key does not appear
        assert config.get("unrelated_var") is None

    def test_env_override_no_known_keys_allows_all(self):
        """If no data loaded yet, all AO_ vars pass through."""
        config = Config()
        os.environ["AO_SOME_KEY"] = "value"
        config._load_env_overrides()
        assert config.get("some.key") == "value"
