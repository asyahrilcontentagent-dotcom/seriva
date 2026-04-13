"""Role implementations for SERIVA.

Setiap role memiliki karakter, gaya bahasa, dan prompt builder sendiri.
"""

from .base_role import BaseRole, Role  # noqa: F401
from .nova import NovaRole  # noqa: F401
from .ipar_tasha import IparTashaRole  # noqa: F401
from .teman_kantor_ipeh import TemanKantorIpehRole  # noqa: F401
from .teman_lama_widya import TemanLamaWidyaRole  # noqa: F401
from .wanita_bersuami_siska import SiskaRole  # noqa: F401
from .terapis_aghia import TerapisAghiaRole  # noqa: F401
from .terapis_munira import TerapisMuniraRole  # noqa: F401
from .teman_spesial_davina import TemanSpesialDavinaRole  # noqa: F401
from .teman_spesial_sallsa import TemanSpesialSallsaRole  # noqa: F401
from .role_registry import ROLE_REGISTRY, get_role  # noqa: F401

__all__ = [
    "BaseRole",
    "Role",
    "NovaRole",
    "IparTashaRole",
    "TemanKantorIpehRole",
    "TemanLamaWidyaRole",
    "SiskaRole",
    "TerapisAghiaRole",
    "TerapisMuniraRole",
    "TemanSpesialDavinaRole",
    "TemanSpesialSallsaRole",
    "ROLE_REGISTRY",
    "get_role",
]
