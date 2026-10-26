"""FSRS-4.5 记忆调度。

为什么不用 SM-2：SM-2 只用 ease factor + 固定间隔，无法区分「简单但忘记」与
「困难但记得」。FSRS 为每个知识点维护三个量：

    stability  S —— 记忆稳定度，可理解为「回忆概率降到 90% 所需天数」
    difficulty D —— 该知识点的固有难度，1~10
    retrievability R —— 当前可回忆概率，由 S 与距上次复习的天数算出

    R(t, S) = (1 + FACTOR * t / S) ^ DECAY

评分（rating）沿用 FSRS 四级：
    1 again（忘了）  2 hard（吃力）  3 good（记得）  4 easy（太简单）

公式参数采用 FSRS-4.5 公开默认权重。所有阈值集中在本文件，便于审计。
"""
from __future__ import annotations

import math
import random
from datetime import datetime, timedelta

W = [
    0.4872, 1.4003, 3.7145, 13.8206, 5.1618, 1.2298, 0.8975, 0.031,
    1.6474, 0.1367, 1.0461, 2.1072, 0.0793, 0.3246, 1.587, 0.2272, 2.8755,
]
DECAY = -0.5
FACTOR = 0.9 ** (1 / DECAY) - 1  # ≈ 0.2346
MIN_STABILITY = 0.1
MAX_STABILITY = 36500.0
RELEARN_MINUTES = 10
LEECH_THRESHOLD = 4


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def retrievability(elapsed_days: float, stability: float) -> float:
    if stability <= 0:
        return 0.0
    elapsed = max(0.0, elapsed_days)
    return (1 + FACTOR * elapsed / stability) ** DECAY


def init_stability(rating: int) -> float:
    return clamp(W[rating - 1], MIN_STABILITY, MAX_STABILITY)


def init_difficulty(rating: int) -> float:
    return clamp(W[4] - (rating - 3) * W[5], 1.0, 10.0)


def next_difficulty(d: float, rating: int) -> float:
    d2 = d - W[6] * (rating - 3)
    # 向初始难度均值回归，避免难度单调发散
    return clamp(W[7] * init_difficulty(4) + (1 - W[7]) * d2, 1.0, 10.0)


def next_stability_recall(d: float, s: float, r: float, rating: int) -> float:
    hard_penalty = W[15] if rating == 2 else 1.0
    easy_bonus = W[16] if rating == 4 else 1.0
    s2 = s * (
        1
        + math.exp(W[8])
        * (11 - d)
        * (s ** -W[9])
        * (math.exp((1 - r) * W[10]) - 1)
        * hard_penalty
        * easy_bonus
    )
    return clamp(s2, MIN_STABILITY, MAX_STABILITY)


def next_stability_forget(d: float, s: float, r: float) -> float:
    s2 = W[11] * (d ** -W[12]) * ((s + 1) ** W[13] - 1) * math.exp((1 - r) * W[14])
    return clamp(s2, MIN_STABILITY, MAX_STABILITY)


def interval_days(stability: float, retention: float = 0.9) -> float:
    """在目标留存率下应间隔的天数。retention=0.9 时间隔约等于 stability。"""
    retention = clamp(retention, 0.7, 0.99)
    iv = (stability / FACTOR) * (retention ** (1 / DECAY) - 1)
    return clamp(iv, 0.02, 3650.0)


def fuzz(iv: float) -> float:
    """长间隔加 ±5% 抖动，避免大量卡片挤在同一天。"""
    if iv < 2:
        return iv
    return iv * random.uniform(0.95, 1.05)


def schedule(
    card: dict | None,
    rating: int,
    now: datetime,
    retention: float = 0.9,
) -> dict:
    """根据本次评分推进一张卡片，返回新状态。card 为 None 表示首次学习。"""
    rating = int(clamp(rating, 1, 4))

    if not card or card.get("state") in (None, "new") or not card.get("stability"):
        s = init_stability(rating)
        d = init_difficulty(rating)
        lapses = 1 if rating == 1 else 0
        if rating == 1:
            state = "relearn"
            iv = RELEARN_MINUTES / 1440
        elif rating == 2:
            state = "review"
            iv = max(interval_days(s, retention) * 0.5, 0.35)
        elif rating == 3:
            state = "review"
            iv = max(interval_days(s, retention) * 0.8, 0.5)
        else:
            state = "review"
            iv = max(interval_days(s, retention), 1.0)
        return {
            "state": state,
            "stability": s,
            "difficulty": d,
            "reps": 1,
            "lapses": lapses,
            "leech": 0,
            "interval_days": iv,
            "due_at": now + timedelta(days=iv),
            "last_review": now,
            "prev_stability": 0.0,
        }

    s = float(card["stability"])
    d = float(card["difficulty"])
    prev_state = card.get("state") or "review"
    lapses = int(card.get("lapses") or 0)
    leech = int(card.get("leech") or 0)
    last = card.get("last_review")
    elapsed = 0.0
    if isinstance(last, datetime):
        elapsed = max(0.0, (now - last).total_seconds() / 86400)
    r = retrievability(elapsed, s) if elapsed else 1.0

    if rating == 1:
        s2 = next_stability_forget(d, s, r)
        d2 = next_difficulty(d, rating)
        lapses += 1
        state = "relearn"
        iv = RELEARN_MINUTES / 1440
        if lapses >= LEECH_THRESHOLD:
            leech = 1
    else:
        s2 = next_stability_recall(d, s, r, rating)
        d2 = next_difficulty(d, rating)
        state = "review"
        iv = fuzz(interval_days(s2, retention))
        if prev_state in ("relearn", "learning"):
            iv = max(iv * 0.6, 0.5)
        else:
            iv = max(iv, 1.0)

    return {
        "state": state,
        "stability": s2,
        "difficulty": d2,
        "reps": int(card.get("reps") or 0) + 1,
        "lapses": lapses,
        "leech": leech,
        "interval_days": iv,
        "due_at": now + timedelta(days=iv),
        "last_review": now,
        "prev_stability": s,
    }


def rating_from_accuracy(acc: float) -> int:
    """把一次训练的正确率折算成 FSRS 评分。阈值与档位在此集中定义。"""
    if acc >= 0.85:
        return 4
    if acc >= 0.67:
        return 3
    if acc >= 0.34:
        return 2
    return 1


def combine_rating(self_rating: int | None, acc: float) -> int:
    """复习时综合「自评回忆」与「实测正确率」，取更保守的一方。

    自评容易高估，实测容易受单题运气影响，两者取 min 可以同时抑制
    虚假熟练与偶发失误，调度更稳。
    """
    acc_rating = rating_from_accuracy(acc)
    if not self_rating:
        return acc_rating
    return min(int(self_rating), acc_rating)


def mastery(card: dict | None, accuracy: float, coverage: float, now: datetime) -> float:
    """掌握度 0~100，四项加权。

    stability 贡献 30%：S 到 45 天视为满档（约等于半年不忘）
    近期正确率 30%：来自最近 10 次作答
    题目覆盖 15%：做过 4 道以上不同题目视为满档
    当前可回忆概率 25%：避免「曾经学过但现在已经忘了」仍显示高掌握
    """
    if not card or not card.get("stability"):
        return 0.0
    s = float(card["stability"])
    last = card.get("last_review")
    r = 1.0
    if isinstance(last, datetime):
        r = retrievability((now - last).total_seconds() / 86400, s)
    m = 0.30 * min(s / 45.0, 1.0) + 0.30 * clamp(accuracy, 0, 1) + 0.15 * clamp(coverage, 0, 1) + 0.25 * r
    return round(100 * m, 1)


def status_of(card: dict | None, m: float) -> str:
    if not card or not card.get("stability"):
        return "new"
    if card.get("leech"):
        return "leech"
    if card.get("state") in ("relearn", "learning"):
        return "relearning"
    if m >= 80:
        return "mastered"
    return "review"
