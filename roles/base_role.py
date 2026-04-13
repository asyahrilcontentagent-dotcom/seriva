"""Base role class untuk semua role SERIVA."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from core.state_models import RoleState, UserState
from prompts.role_specs import RolePromptSpec
from prompts.unified_prompt import build_unified_system_prompt


class Role(Protocol):  # pragma: no cover - interface
    role_id: str

    def build_messages(self, user_state: UserState, role_state: RoleState, user_text: str) -> list[dict]:
        """Bangun daftar messages untuk dikirim ke LLM."""
        ...


@dataclass
class BaseRole:
    """Implementasi dasar yang bisa dipakai role-role lain."""

    role_id: str

    def get_prompt_spec(self) -> RolePromptSpec:  # pragma: no cover - override di subclass
        raise NotImplementedError

    def build_messages(self, user_state: UserState, role_state: RoleState, user_text: str) -> list[dict]:  # pragma: no cover - override di subclass
        spec = self.get_prompt_spec()
        system_prompt = build_unified_system_prompt(
            role_state=role_state,
            role_name=spec.role_name,
            relationship_status=spec.relationship_status,
            scenario_context=spec.scenario_context,
            knowledge_boundary=spec.knowledge_boundary,
            role_personality=spec.personality,
            vulgar_allowed=spec.vulgar_allowed,
            extra_rules=spec.extra_rules,
        )
        user_prompt = spec.build_user_prompt(user_text)
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
