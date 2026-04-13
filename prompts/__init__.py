"""Prompt builders for SERIVA roles.

Masing-masing file di sini membangun system prompt & user prefix untuk satu role.
"""

from .nova_prompt import build_nova_system_prompt, build_nova_user_prompt_prefix  # noqa: F401
from .ipar_tasha_prompt import (  # noqa: F401
    build_ipar_tasha_system_prompt,
    build_ipar_tasha_user_prompt_prefix,
)
from .teman_kantor_ipeh_prompt import (  # noqa: F401
    build_teman_kantor_ipeh_system_prompt,
    build_teman_kantor_ipeh_user_prompt_prefix,
)
from .teman_lama_widya_prompt import (  # noqa: F401
    build_teman_lama_widya_system_prompt,
    build_teman_lama_widya_user_prompt_prefix,
)
from .wanita_bersuami_siska_prompt import (  # noqa: F401
    build_siska_system_prompt,
    build_siska_user_prompt_prefix,
)
from .terapis_aghia_prompt import (  # noqa: F401
    build_terapis_aghia_system_prompt,
    build_terapis_aghia_user_prompt_prefix,
)
from .terapis_munira_prompt import (  # noqa: F401
    build_terapis_munira_system_prompt,
    build_terapis_munira_user_prompt_prefix,
)
from .teman_spesial_davina_prompt import (  # noqa: F401
    build_teman_spesial_davina_system_prompt,
    build_teman_spesial_davina_user_prompt_prefix,
)
from .teman_spesial_sallsa_prompt import (  # noqa: F401
    build_teman_spesial_sallsa_system_prompt,
    build_teman_spesial_sallsa_user_prompt_prefix,
)

__all__ = [
    "build_nova_system_prompt",
    "build_nova_user_prompt_prefix",
    "build_ipar_tasha_system_prompt",
    "build_ipar_tasha_user_prompt_prefix",
    "build_teman_kantor_ipeh_system_prompt",
    "build_teman_kantor_ipeh_user_prompt_prefix",
    "build_teman_lama_widya_system_prompt",
    "build_teman_lama_widya_user_prompt_prefix",
    "build_siska_system_prompt",
    "build_siska_user_prompt_prefix",
    "build_terapis_aghia_system_prompt",
    "build_terapis_aghia_user_prompt_prefix",
    "build_terapis_munira_system_prompt",
    "build_terapis_munira_user_prompt_prefix",
    "build_teman_spesial_davina_system_prompt",
    "build_teman_spesial_davina_user_prompt_prefix",
    "build_teman_spesial_sallsa_system_prompt",
    "build_teman_spesial_sallsa_user_prompt_prefix",
]
