"""Role implementation for Widya (teman_lama_widya)."""

from __future__ import annotations

from dataclasses import dataclass

from config.constants import ROLE_ID_TEMAN_LAMA_WIDYA
from prompts.role_specs import RolePromptSpec, get_role_prompt_spec
from roles.base_role import BaseRole


@dataclass
class TemanLamaWidyaRole(BaseRole):
    role_id: str = ROLE_ID_TEMAN_LAMA_WIDYA

    def get_prompt_spec(self) -> RolePromptSpec:
        return get_role_prompt_spec(self.role_id)
