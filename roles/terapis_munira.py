"""Role implementation for Munira (terapis_munira)."""

from __future__ import annotations

from dataclasses import dataclass

from config.constants import ROLE_ID_TERAPIS_MUNIRA
from prompts.role_specs import RolePromptSpec, get_role_prompt_spec
from roles.base_role import BaseRole


@dataclass
class TerapisMuniraRole(BaseRole):
    role_id: str = ROLE_ID_TERAPIS_MUNIRA

    def get_prompt_spec(self) -> RolePromptSpec:
        return get_role_prompt_spec(self.role_id)
