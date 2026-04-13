"""Role implementation for Nova."""

from __future__ import annotations

from dataclasses import dataclass

from config.constants import ROLE_ID_NOVA
from prompts.role_specs import RolePromptSpec, get_role_prompt_spec
from roles.base_role import BaseRole


@dataclass
class NovaRole(BaseRole):
    role_id: str = ROLE_ID_NOVA

    def get_prompt_spec(self) -> RolePromptSpec:
        return get_role_prompt_spec(self.role_id)
