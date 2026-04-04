"""Strategy contract: ``(entry_signal, exit_signal)`` aligned to ``df.index``."""

from __future__ import annotations

from typing import Protocol

import pandas as pd


class Strategy(Protocol):
    def __call__(self, df: pd.DataFrame, /) -> tuple[pd.Series, pd.Series]:
        """
        Returns ``entry_signal`` and ``exit_signal``, each a boolean ``pd.Series``
        indexed exactly like ``df``.
        """
