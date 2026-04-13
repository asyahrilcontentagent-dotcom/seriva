"""World engine for SERIVA.

Mengelola state global di dunia SERIVA:
- drama_level: seberapa panas/dramatis dunia secara umum (0–100)
- world events: log singkat kejadian penting lintas role

Fungsi utama:
- update_drama_on_cross_role():
    efek ketika user pindah dari satu role ke role lain (bisa picu drama)
- decay_drama():
    menurunkan drama pelan-pelan seiring waktu (dipanggil worker)
- log_event():
    menyimpan event untuk referensi flashback global atau analisis
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.state_models import WorldEvent, WorldState
from config.constants import MIN_DRAMA_LEVEL, MAX_DRAMA_LEVEL


def _clamp(value: int, min_v: int, max_v: int) -> int:
    return max(min_v, min(max_v, value))


@dataclass
class CrossRoleContext:
    """Konteks ketika user berpindah atau aktif intens dengan role lain.

    Contoh:
    - dari Nova ke teman_spesial_davina
    - dari Nova ke ipar_tasha

    `reason` bisa bantu beda efek: penasaran, pelarian, konflik, dll.
    """

    user_id: str
    from_role_id: Optional[str]
    to_role_id: str
    reason: str = "switch"  # bebas, dipakai buat deskripsi event


class WorldEngine:
    """Mesin pengelola WorldState SERIVA."""

    # seberapa besar kenaikan drama saat cross-role
    BASE_DRAMA_SPIKE = 5
    EXTRA_DRAMA_FOR_FORBIDDEN = 5  # ipar, wanita bersuami, teman spesial

    # seberapa cepat drama turun per hari (dipanggil worker)
    DRAMA_DECAY_PER_DAY = 6

    def increase_drama(self, world: WorldState, amount: int) -> None:
        world.drama_level = _clamp(world.drama_level + amount, MIN_DRAMA_LEVEL, MAX_DRAMA_LEVEL)

    def decrease_drama(self, world: WorldState, amount: int) -> None:
        world.drama_level = _clamp(world.drama_level - amount, MIN_DRAMA_LEVEL, MAX_DRAMA_LEVEL)

    def update_drama_on_cross_role(
        self,
        world: WorldState,
        ctx: CrossRoleContext,
        *,
        now_ts: float,
    ) -> None:
        """Dipanggil saat user pindah/gas interaksi dengan role lain.

        Logika umum:
        - Selalu ada kenaikan drama kecil.
        - Jika to_role_id termasuk kategori "forbidden" (ipar, wanita bersuami,
          teman spesial), tambahkan drama ekstra.
        - Simpan event deskriptif di world.events.
        """

        from seriva.config.constants import ROLES  # import lokal untuk hindari cycle

        base_spike = self.BASE_DRAMA_SPIKE
        extra = 0

        to_info = ROLES.get(ctx.to_role_id)
        if to_info is not None:
            if to_info.category in {"IPAR", "WANITA_BERSUAMI", "TEMAN_SPESIAL"}:
                extra += self.EXTRA_DRAMA_FOR_FORBIDDEN

        spike = base_spike + extra
        self.increase_drama(world, spike)

        # Buat deskripsi event yang aman (non-vulgar, high-level)
        if ctx.from_role_id is not None and ctx.from_role_id in ROLES:
            from_info = ROLES[ctx.from_role_id]
            from_name = from_info.display_name
        else:
            from_name = None

        to_name = to_info.display_name if to_info else ctx.to_role_id

        if from_name:
            desc = f"User berpindah dari {from_name} ke {to_name} ({ctx.reason})."
        else:
            desc = f"User memulai interaksi dengan {to_name} ({ctx.reason})."

        event = WorldEvent(
            timestamp=now_ts,
            user_id=ctx.user_id,
            role_id=ctx.to_role_id,
            description=desc,
        )
        world.add_event(event)
        world.clamp()

    def decay_drama(
        self,
        world: WorldState,
        days_passed: float,
    ) -> None:
        """Turunkan drama seiring waktu (dipanggil background worker).

        Makin lama tidak ada kejadian besar, dunia jadi lebih tenang.
        """

        if days_passed <= 0:
            return

        amount = int(self.DRAMA_DECAY_PER_DAY * days_passed)
        self.decrease_drama(world, amount)

    def log_custom_event(
        self,
        world: WorldState,
        *,
        timestamp: float,
        user_id: str,
        role_id: str,
        description: str,
    ) -> None:
        """Simpan event kustom lain yang penting.

        Misalnya:
        - "Nova pertama kali bilang sayang"
        - "Siska curhat tentang rumah tangganya"
        - Digunakan kemudian untuk flashback global.
        """

        event = WorldEvent(
            timestamp=timestamp,
            user_id=user_id,
            role_id=role_id,
            description=description,
        )
        world.add_event(event)
        world.clamp()

    def update_household_awareness(
        self,
        world: WorldState,
        *,
        text: str,
        timestamp: float,
    ) -> bool:
        """Perbarui awareness rumah bersama dari teks user."""

        lowered = text.lower()
        changed = False

        nova_away_markers = [
            "nova lagi keluar",
            "nova lagi pergi",
            "istriku lagi keluar",
            "istriku lagi pergi",
            "kakakmu lagi keluar",
            "kakakmu lagi pergi",
            "nova gak di rumah",
        ]
        nova_home_markers = [
            "nova di rumah",
            "istriku di rumah",
            "kakakmu di rumah",
            "nova lagi di rumah",
            "nova baru pulang",
        ]
        private_markers = [
            "cuma berdua",
            "lagi berdua",
            "sendirian",
            "rumah sepi",
            "aman nih",
        ]
        guarded_markers = [
            "rumah lagi ramai",
            "ada orang",
            "banyak orang",
            "jangan ketahuan",
            "pelan ya",
            "suara kecil",
        ]

        if any(marker in lowered for marker in nova_away_markers):
            world.nova_is_home = False
            world.current_household_note = "Nova sedang tidak di rumah; suasana lebih longgar tapi tetap harus masuk akal."
            changed = True
        elif any(marker in lowered for marker in nova_home_markers):
            world.nova_is_home = True
            world.current_household_note = "Nova sedang di rumah; interaksi rumah tangga harus lebih hati-hati."
            changed = True

        if any(marker in lowered for marker in private_markers):
            world.house_privacy_level = "private"
            changed = True
        elif any(marker in lowered for marker in guarded_markers):
            world.house_privacy_level = "guarded"
            changed = True

        if "dietha lagi keluar" in lowered or "dietha gak di rumah" in lowered:
            world.dietha_is_home = False
            changed = True
        elif "dietha di rumah" in lowered or "dietha baru pulang" in lowered:
            world.dietha_is_home = True
            changed = True

        if changed:
            world.last_household_update_ts = timestamp
        return changed
