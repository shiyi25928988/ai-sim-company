"""Shared application singletons - config + CompanyHub.

Exists as a separate module to break the server <-> routes circular import:
both server and routes take `hub` from here, with no dependency on each other.
"""

from __future__ import annotations

from aisim.company.hub import CompanyHub
from aisim.shared.config import load_config

config = load_config("config/company.yaml")
hub = CompanyHub(config)
