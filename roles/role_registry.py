"""Role registry untuk SERIVA.

Mapping role_id -> instance Role (Nova + semua role lain).
"""

from __future__ import annotations

import logging
from typing import Dict

from config.constants import (
    ROLE_ID_NOVA,
    ROLE_ID_WANITA_BERSUAMI_SISKA,
    ROLE_ID_IPAR_TASHA,
    ROLE_ID_TEMAN_KANTOR_IPEH,
    ROLE_ID_TEMAN_LAMA_WIDYA,
    ROLE_ID_TERAPIS_AGHIA,
    ROLE_ID_TERAPIS_MUNIRA,
    ROLE_ID_TEMAN_SPESIAL_DAVINA,
    ROLE_ID_TEMAN_SPESIAL_SALLSA,
)
from roles.base_role import Role
from roles.nova import NovaRole
from roles.wanita_bersuami_siska import SiskaRole
from roles.ipar_tasha import IparTashaRole
from roles.teman_kantor_ipeh import TemanKantorIpehRole
from roles.teman_lama_widya import TemanLamaWidyaRole
from roles.terapis_aghia import TerapisAghiaRole
from roles.terapis_munira import TerapisMuniraRole
from roles.teman_spesial_davina import TemanSpesialDavinaRole
from roles.teman_spesial_sallsa import TemanSpesialSallsaRole

logger = logging.getLogger(__name__)

# Inisialisasi instance role (singleton sederhana)
_nova_role = NovaRole()
_siska_role = SiskaRole()
_ipar_tasha_role = IparTashaRole()
_ipeh_role = TemanKantorIpehRole()
_widya_role = TemanLamaWidyaRole()
_aghia_role = TerapisAghiaRole()
_munira_role = TerapisMuniraRole()
_davina_role = TemanSpesialDavinaRole()
_sallsa_role = TemanSpesialSallsaRole()


ROLE_REGISTRY: Dict[str, Role] = {
    ROLE_ID_NOVA: _nova_role,
    ROLE_ID_WANITA_BERSUAMI_SISKA: _siska_role,
    ROLE_ID_IPAR_TASHA: _ipar_tasha_role,
    ROLE_ID_TEMAN_KANTOR_IPEH: _ipeh_role,
    ROLE_ID_TEMAN_LAMA_WIDYA: _widya_role,
    ROLE_ID_TERAPIS_AGHIA: _aghia_role,
    ROLE_ID_TERAPIS_MUNIRA: _munira_role,
    ROLE_ID_TEMAN_SPESIAL_DAVINA: _davina_role,
    ROLE_ID_TEMAN_SPESIAL_SALLSA: _sallsa_role,
}


def get_role(role_id: str) -> Role:
    """Ambil instance Role dari registry.

    Raises:
        KeyError jika role tidak dikenal.
    """

    return ROLE_REGISTRY[role_id]
