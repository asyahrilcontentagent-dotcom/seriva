from __future__ import annotations

from core.scene_engine import SceneEngine, SceneUpdateRequest
from core.state_models import RoleState


class SceneManager:
    """Koordinator ringan untuk decay dan prioritas scene."""

    def __init__(self, scene_engine: SceneEngine | None = None) -> None:
        self.scene_engine = scene_engine or SceneEngine()

    def prepare_for_turn(self, role_state: RoleState, now_ts: float) -> None:
        self.scene_engine.apply_decay(role_state.scene, now_ts=now_ts)

    def mark_focus(self, role_state: RoleState, amount: int = 1) -> None:
        self.scene_engine.bump_priority(role_state.scene, amount=amount)

    def apply_context_awareness(
        self,
        role_state: RoleState,
        user_text: str,
        now_ts: float,
    ) -> None:
        """Sesuaikan scene dengan sinyal konteks sederhana dari pesan user."""

        text = user_text.lower()
        update = SceneUpdateRequest()
        touched = False

        if any(keyword in text for keyword in ["cepet", "buru", "sebentar", "singkat"]):
            update.ambience = "suasana terasa lebih cepat dan serba singkat"
            touched = True
        elif any(keyword in text for keyword in ["tenang", "pelan", "santai", "dulu aja"]):
            update.ambience = "suasana lebih tenang dan ritmenya melambat"
            touched = True

        if any(keyword in text for keyword in ["capek", "lelah", "ngantuk"]):
            update.activity = role_state.scene.activity or "mengobrol singkat sambil menenangkan suasana"
            update.physical_distance = role_state.scene.physical_distance or "sebelahan dengan jarak nyaman"
            touched = True

        if touched:
            update.priority = min(10, max(1, role_state.scene.scene_priority + 1))
            self.scene_engine.apply_update(role_state.scene, update, now_ts=now_ts)
