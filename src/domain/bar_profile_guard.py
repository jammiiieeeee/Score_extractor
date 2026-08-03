from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class BarProfileVerdict:
    spikes: List[Tuple[int, float]]
    is_clean: bool
    has_left_spike: bool


class BarProfileGuard:

    @staticmethod
    def from_spikes(spikes, left_margin_ratio: float = 0.35):
        is_clean = len(spikes) == 0 or len(spikes) == 2
        has_left_spike = True
        if len(spikes) >= 2:
            left_col = sorted(spikes[:2], key=lambda p: p[0])[0][0]
            margin_col = int(640 * left_margin_ratio)
            has_left_spike = left_col < margin_col
        return BarProfileVerdict(spikes=spikes, is_clean=is_clean, has_left_spike=has_left_spike)

    @staticmethod
    def is_gold_sample(spikes, is_duplicate: bool, has_left_spike: bool) -> bool:
        return len(spikes) == 2 and not is_duplicate and has_left_spike
