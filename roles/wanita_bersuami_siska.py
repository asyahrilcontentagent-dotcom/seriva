"""Role implementation for Siska (wanita bersuami)."""

from __future__ import annotations

from dataclasses import dataclass

from config.constants import ROLE_ID_WANITA_BERSUAMI_SISKA
from prompts.role_specs import RolePromptSpec, get_role_prompt_spec
from roles.base_role import BaseRole


@dataclass
class SiskaRole(BaseRole):
    role_id: str = ROLE_ID_WANITA_BERSUAMI_SISKA

    def get_prompt_spec(self) -> RolePromptSpec:
        return get_role_prompt_spec(self.role_id)
