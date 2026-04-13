"""Role: Teman kantor dekat (Musdalifah / Ipeh)."""

from __future__ import annotations

from dataclasses import dataclass

from config.constants import ROLE_ID_TEMAN_KANTOR_IPEH
from prompts.role_specs import RolePromptSpec, get_role_prompt_spec
from roles.base_role import BaseRole


@dataclass
class TemanKantorIpehRole(BaseRole):
    role_id: str = ROLE_ID_TEMAN_KANTOR_IPEH
    display_name: str = "Teman kantor dekat (Musdalifah / Ipeh)"

    def get_prompt_spec(self) -> RolePromptSpec:
        return get_role_prompt_spec(self.role_id)
