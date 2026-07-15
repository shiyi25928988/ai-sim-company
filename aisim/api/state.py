"""共享的应用单例 - config + CompanyHub。

单独成模块以打破 server <-> routes 的循环导入:
server 与 routes 都从这里取 `hub`，互不依赖。
"""

from __future__ import annotations

from aisim.company.hub import CompanyHub
from aisim.shared.config import load_config

config = load_config("config/company.yaml")
hub = CompanyHub(config)
