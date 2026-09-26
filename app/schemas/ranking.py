"""Ranking schemas."""

from __future__ import annotations

from pydantic import BaseModel


class RankingEntry(BaseModel):
    rank: int
    user_id: int
    display_name: str
    username: str | None = None
    points: int
    activities: int


class MyRankingOut(BaseModel):
    rank: int
    total_users: int
    points: int
    streak_count: int
    activities: int
