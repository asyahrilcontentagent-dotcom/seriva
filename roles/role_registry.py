"""Role registry untuk SERIVA companion mode 4 role."""

from __future__ import annotations

import logging
from typing import Dict

from config.constants import (
    ROLE_ID_WANITA_BERSUAMI_SISKA,
    ROLE_ID_IPAR_TASHA,
    ROLE_ID_TEMAN_KANTOR_IPEH,
    ROLE_ID_TEMAN_LAMA_WIDYA,
)
from roles.base_role import Role
from roles.wanita_bersuami_siska import SiskaRole
from roles.ipar_tasha import IparTashaRole
from roles.teman_kantor_ipeh import TemanKantorIpehRole
from roles.teman_lama_widya import TemanLamaWidyaRole

logger = logging.getLogger(__name__)

_siska_role = SiskaRole()
_ipar_tasha_role = IparTashaRole()
_ipeh_role = TemanKantorIpehRole()
_widya_role = TemanLamaWidyaRole()


ROLE_REGISTRY: Dict[str, Role] = {
    ROLE_ID_WANITA_BERSUAMI_SISKA: _siska_role,
    ROLE_ID_IPAR_TASHA: _ipar_tasha_role,
    ROLE_ID_TEMAN_KANTOR_IPEH: _ipeh_role,
    ROLE_ID_TEMAN_LAMA_WIDYA: _widya_role,
}


def get_role(role_id: str) -> Role:
    """Ambil instance Role dari registry.

    Raises:
        KeyError jika role tidak dikenal.
    """

    return ROLE_REGISTRY[role_id]
