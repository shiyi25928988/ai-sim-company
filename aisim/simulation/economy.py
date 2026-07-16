"""Economy system - income/expenses / salary / funding / bankruptcy detection (see §三)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class EconomyState:
    capital: int = 0
    monthly_burn: int = 0  # Monthly burn (total salary + operating costs)
    revenue: int = 0
    history: list[dict] = field(default_factory=list)
    bankrupt: bool = False


class EconomyEngine:
    """Company finance simulation."""

    def __init__(self, initial_capital: int = 500_000) -> None:
        self.state = EconomyState(capital=initial_capital)

    def add_salary(self, salary: int) -> None:
        """When adding a new Agent, accumulate its salary into the monthly burn."""
        self.state.monthly_burn += salary

    def remove_salary(self, salary: int) -> None:
        self.state.monthly_burn = max(0, self.state.monthly_burn - salary)

    def apply_tick(self, tick: int) -> None:
        """Settle each Tick: deduct costs / bookkeeping / bankruptcy detection.

        Assumes 720 Ticks/month (1 Tick≈1 hour), deducted linearly by monthly burn.
        """
        per_tick = self.state.monthly_burn / 720
        self.state.capital -= int(per_tick)
        self.state.history.append({"tick": tick, "capital": self.state.capital})
        if self.state.capital <= 0:
            self.state.capital = 0
            self.state.bankrupt = True
            logger.warning("公司破产! tick=%d", tick)

    def receive_funding(self, amount: int) -> None:
        """Funding received."""
        self.state.capital += amount
        logger.info("融资入账: +%d -> %d", amount, self.state.capital)

    def snapshot(self) -> dict:
        return {
            "capital": self.state.capital,
            "monthly_burn": self.state.monthly_burn,
            "revenue": self.state.revenue,
            "bankrupt": self.state.bankrupt,
        }
