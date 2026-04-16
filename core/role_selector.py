from __future__ import annotations

from core.state_models import RoleState, UserState
from prompts.role_specs import get_role_prompt_spec


class RoleSelector:
    """Helper kecil untuk menjaga pemilihan role tetap terpusat."""

    def get_active_role_state(self, user_state: UserState) -> RoleState:
        role_state = user_state.get_or_create_role_state(user_state.active_role_id)
        spec = get_role_prompt_spec(role_state.role_id)
        if not role_state.role_display_name:
            role_state.role_display_name = spec.role_name
        return role_state
