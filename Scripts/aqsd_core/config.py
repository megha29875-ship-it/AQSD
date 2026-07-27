"""
AQSD
Configuration Manager

Module    : config.py
Module ID : CORE-002
Version   : 1.0.0
Author    : AQSD
Status    : Production

Description
-----------
Loads and validates AQSD configuration from config.yaml.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .constants import CONFIG_DIR


class ConfigurationError(Exception):
    """Raised when configuration is invalid."""


class Config:

    def __init__(self, filename: str = "config.yaml") -> None:

        self.file_path = CONFIG_DIR / filename
        self.settings: dict[str, Any] = {}

    def load(self) -> dict[str, Any]:
        """Load configuration file."""

        if not self.file_path.exists():
            raise ConfigurationError(
                f"Configuration file not found : {self.file_path}"
            )

        with open(self.file_path, "r", encoding="utf-8") as file:
            self.settings = yaml.safe_load(file)

        self.validate()

        return self.settings

    def validate(self) -> None:
        """Validate required configuration."""

        required = [

            "project",

            "paths",

            "database",

            "logging",

            "calendar",

        ]

        for key in required:

            if key not in self.settings:

                raise ConfigurationError(

                    f"Missing configuration section : {key}"

                )

    def get(self, key: str, default: Any = None) -> Any:
        """Return configuration value."""

        return self.settings.get(key, default)


config = Config()