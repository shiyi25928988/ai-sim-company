"""经济系统 - 收支 / 薪资 / 融资 / 破产判定 (见 §三)。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class EconomyState:
    capital: int = 0
    monthly_burn: int = 0  # 月烧钱 (薪资合计 + 运营成本)
    revenue: int = 0
    history: list[dict] = field(default_factory=list)
    bankrupt: bool = False


class EconomyEngine:
    """公司财务模拟。"""

    def __init__(self, initial_capital: int = 500_000) -> None:
        self.state = EconomyState(capital=initial_capital)

    def add_salary(self, salary: int) -> None:
        """新增 Agent 时累加其薪资到月烧钱。"""
        self.state.monthly_burn += salary

    def remove_salary(self, salary: int) -> None:
        self.state.monthly_burn = max(0, self.state.monthly_burn - salary)

    def apply_tick(self, tick: int) -> None:
        """每个 Tick 结算: 扣减成本 / 记账 / 破产判定。

        假设 720 Tick/月 (1 Tick≈1小时)，按月烧钱线性扣减。
        """
        per_tick = self.state.monthly_burn / 720
        self.state.capital -= int(per_tick)
        self.state.history.append({"tick": tick, "capital": self.state.capital})
        if self.state.capital <= 0:
            self.state.capital = 0
            self.state.bankrupt = True
            logger.warning("公司破产! tick=%d", tick)

    def receive_funding(self, amount: int) -> None:
        """融资入账。"""
        self.state.capital += amount
        logger.info("融资入账: +%d -> %d", amount, self.state.capital)

    def snapshot(self) -> dict:
        return {
            "capital": self.state.capital,
            "monthly_burn": self.state.monthly_burn,
            "revenue": self.state.revenue,
            "bankrupt": self.state.bankrupt,
        }
