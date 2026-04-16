from __future__ import annotations

from core.scene_engine import SceneEngine
from core.state_models import RoleState


class SceneManager:
    """Koordinator ringan untuk decay dan prioritas scene."""

    def __init__(self, scene_engine: SceneEngine | None = None) -> None:
        self.scene_engine = scene_engine or SceneEngine()

    def prepare_for_turn(self, role_state: RoleState, now_ts: float) -> None:
        self.scene_engine.apply_decay(role_state.scene, now_ts=now_ts)

    def mark_focus(self, role_state: RoleState, amount: int = 1) -> None:
        self.scene_engine.bump_priority(role_state.scene, amount=amount)
