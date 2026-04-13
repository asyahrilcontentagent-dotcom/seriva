"""Role implementation for Tasha Dietha (ipar_tasha)."""

from __future__ import annotations

from dataclasses import dataclass

from config.constants import ROLE_ID_IPAR_TASHA
from prompts.role_specs import RolePromptSpec, get_role_prompt_spec
from roles.base_role import BaseRole


@dataclass
class IparTashaRole(BaseRole):
    """Role Dietha: ipar yang dekat dan terlarang."""

    role_id: str = ROLE_ID_IPAR_TASHA

    def get_prompt_spec(self) -> RolePromptSpec:
        return get_role_prompt_spec(self.role_id)
