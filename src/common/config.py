"""Configuration management module."""

import os
import json
from typing import Any, Dict, Optional, Set


class Config:
    def __init__(self, config_path: Optional[str] = None):
        self._data: Dict[str, Any] = {}
        if config_path:
            self.load(config_path)
        self._load_env_overrides()

    def load(self, path: str) -> None:
        with open(path) as f:
            self._data = json.load(f)

    def _known_config_keys(self, prefix: str = "") -> Set[str]:
        """Recursively collect all known config key paths."""
        keys: Set[str] = set()
        for key, value in self._data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            keys.add(full_key)
            if isinstance(value, dict):
                keys.update(self._known_config_keys(full_key))
        return keys

    def _load_env_overrides(self) -> None:
        """Load environment variable overrides, filtering unrelated AO_ variables."""
        prefix = "AO_"
        known_keys = self._known_config_keys()

        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix):].lower().replace("_", ".")

                # Skip variables that don't match any known config path
                if known_keys and config_key not in known_keys:
                    matched = any(config_key.startswith(k) or k.startswith(config_key) for k in known_keys)
                    if not matched:
                        continue

                self._set_nested(config_key, value)

    def _set_nested(self, key: str, value: Any) -> None:
        parts = key.split(".")
        current = self._data
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

    def get(self, key: str, default: Any = None) -> Any:
        parts = key.split(".")
        current = self._data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
                if current is None:
                    return default
            else:
                return default
        return current

    def set(self, key: str, value: Any) -> None:
        self._set_nested(key, value)

    def to_dict(self) -> Dict[str, Any]:
        return self._data
