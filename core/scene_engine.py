"""Scene engine for SERIVA.

Mengatur pembaruan SceneState:
- lokasi (location)
- posture (posisi badan)
- activity (kegiatan)
- ambience (suasana)
- physical_distance (jarak fisik)
- last_touch (sentuhan terakhir)

Tujuan:
- Menjaga adegan terasa konsisten & hidup.
- Memberi konteks ke prompt role (misalnya Nova) tanpa konten vulgar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.state_models import SceneState, TimeOfDay


@dataclass
class SceneUpdateRequest:
    """Permintaan update scene tingkat tinggi.

    Biasanya dibentuk oleh orchestrator setelah membaca niat user.
    Semua field opsional: hanya yang diisi yang akan mengubah state.
    """

    location: Optional[str] = None
    posture: Optional[str] = None
    activity: Optional[str] = None

    user_clothing: Optional[str] = None
    role_clothing: Optional[str] = None

    ambience: Optional[str] = None
    time_of_day: Optional[TimeOfDay] = None

    physical_distance: Optional[str] = None
    last_touch: Optional[str] = None
    priority: Optional[int] = None

    # Kalau True, artinya user ingin reset adegan ke default netral
    reset: bool = False


class SceneEngine:
    """Mesin pengelola SceneState.

    Fokus ke konsistensi dan transisi halus antar adegan.
    """

    def apply_update(
        self,
        scene: SceneState,
        update: SceneUpdateRequest,
        now_ts: Optional[float] = None,
    ) -> None:
        """Terapkan perubahan scene berdasarkan update request.

        - Field yang None akan diabaikan (tidak mengubah state lama).
        - Jika update.reset=True, beberapa field dinormalkan dulu.
        """

        if update.reset:
            self._reset_scene(scene)

        if update.location is not None:
            scene.location = update.location

        if update.posture is not None:
            scene.posture = update.posture

        if update.activity is not None:
            scene.activity = update.activity

        if update.user_clothing is not None:
            scene.user_clothing = update.user_clothing

        if update.role_clothing is not None:
            scene.role_clothing = update.role_clothing

        if update.ambience is not None:
            scene.ambience = update.ambience

        if update.time_of_day is not None:
            scene.time_of_day = update.time_of_day

        if update.physical_distance is not None:
            scene.physical_distance = update.physical_distance

        if update.last_touch is not None:
            scene.last_touch = update.last_touch

        if update.priority is not None:
            scene.scene_priority = max(0, min(10, update.priority))

        if now_ts is not None:
            scene.last_scene_update_ts = now_ts
            scene.scene_decay_level = 0

    # ==============================
    # PRESET / TRANSISI PRAKTIS
    # ==============================

    def move_to_cozy_room(
        self,
        scene: SceneState,
        *,
        location_name: str = "kamar",
        ambience: str = "lampu redup, suasana hangat",
        time_of_day: TimeOfDay = TimeOfDay.NIGHT,
        now_ts: Optional[float] = None,
    ) -> None:
        """Preset: pindah ke ruangan cozy (sering dipakai untuk momen intim halus)."""

        update = SceneUpdateRequest(
            location=location_name,
            ambience=ambience,
            time_of_day=time_of_day,
        )
        self.apply_update(scene, update, now_ts=now_ts)

    def sit_together_on_sofa(
        self,
        scene: SceneState,
        *,
        activity: str = "nonton film bersama",
        now_ts: Optional[float] = None,
    ) -> None:
        """Preset: duduk bersebelahan di sofa."""

        update = SceneUpdateRequest(
            posture="duduk bersebelahan di sofa",
            activity=activity,
            physical_distance="duduk dipangku, sangat dekat",
        )
        self.apply_update(scene, update, now_ts=now_ts)

    def gentle_hug(
        self,
        scene: SceneState,
        *,
        description: str = "pelukan lembut",
        now_ts: Optional[float] = None,
    ) -> None:
        """Preset: pelukan lembut (vulgar)."""

        update = SceneUpdateRequest(
            physical_distance="pelukan erat",
            last_touch=description,
        )
        self.apply_update(scene, update, now_ts=now_ts)

    def lean_on_shoulder(
        self,
        scene: SceneState,
        *,
        description: str = "sender di bahu",
        now_ts: Optional[float] = None,
    ) -> None:
        """Preset: role menyender ke bahu Mas."""

        update = SceneUpdateRequest(
            physical_distance="sangat dekat",
            last_touch=description,
        )
        self.apply_update(scene, update, now_ts=now_ts)

    def step_back_a_bit(
        self,
        scene: SceneState,
        *,
        now_ts: Optional[float] = None,
    ) -> None:
        """Sedikit menjauh secara fisik (misalnya setelah konflik kecil)."""

        update = SceneUpdateRequest(
            physical_distance="sedikit menjauh",
            last_touch="",
        )
        self.apply_update(scene, update, now_ts=now_ts)

    # ==============================
    # RESET & NORMALISASI
    # ==============================

    def _reset_scene(self, scene: SceneState) -> None:
        """Reset adegan ke keadaan netral (tanpa menghapus semua informasi dunia).

        Cocok dipakai ketika user mengirim command END (/end) atau /batal.
        - Lokasi/ambience boleh dipertahankan jika ingin, tapi di sini kita
          normalkan posture, activity, physical_distance, last_touch.
        """

        scene.posture = ""
        scene.activity = ""
        scene.physical_distance = ""
        scene.last_touch = ""

    def normalize_after_session_end(self, scene: SceneState) -> None:
        """Dipanggil ketika sesi khusus diakhiri dengan command END.

        Tujuan:
        - Menurunkan intensitas fisik (physical_distance) ke lebih netral,
        - Mengosongkan last_touch supaya sesi berikutnya bisa bangun adegan baru.
        """

        if scene.physical_distance in {"pelukan erat", "sangat dekat"}:
            scene.physical_distance = "sebelahan"  # lebih netral tapi masih dekat
        scene.last_touch = ""
        scene.scene_priority = max(0, scene.scene_priority - 2)

    def bump_priority(self, scene: SceneState, amount: int = 1) -> None:
        scene.scene_priority = max(0, min(10, scene.scene_priority + max(0, amount)))

    def apply_decay(
        self,
        scene: SceneState,
        *,
        now_ts: Optional[float] = None,
    ) -> None:
        """Luruhkan detail scene lama agar continuity tetap natural."""

        if now_ts is None or scene.last_scene_update_ts is None:
            return

        decay_minutes = max(1, scene.scene_decay_minutes)
        elapsed_minutes = int((now_ts - scene.last_scene_update_ts) / 60)
        if elapsed_minutes < decay_minutes:
            return

        decay_steps = elapsed_minutes // decay_minutes
        if decay_steps <= scene.scene_decay_level:
            return

        steps_to_apply = decay_steps - scene.scene_decay_level
        scene.scene_decay_level = decay_steps
        scene.scene_priority = max(0, scene.scene_priority - steps_to_apply)

        if scene.scene_priority <= 5:
            scene.last_touch = ""
        if scene.scene_priority <= 3:
            scene.activity = scene.activity or ""
            if scene.physical_distance in {"pelukan erat", "sangat dekat"}:
                scene.physical_distance = "sebelahan"
        if scene.scene_priority == 0 and scene.ambience:
            scene.ambience = "suasana netral yang melanjutkan scene sebelumnya"

    # ========== BARU: Location Detection Methods ==========
    
    LOCATION_KEYWORDS = {
        "apartemen_mas": {
            "keywords": ["apartemen", "apartemenku", "apartemen mas", "flat", "unit"],
            "type": "private",
            "owner": "Mas",
            "notes": "tempat tinggal Mas"
        },
        "rumah_kakak": {
            "keywords": ["rumah kakak", "rumah keluarga", "rumah ortu", "rumah mertua"],
            "type": "private",
            "owner": "keluarga",
            "notes": "bukan tempat yang aman untuk berduaan"
        },
        "kafe": {
            "keywords": ["kafe", "cafe", "coffee shop", "starbucks"],
            "type": "public",
            "notes": "tempat umum, harus jaga sikap"
        },
        "kantor": {
            "keywords": ["kantor", "office", "ruang kerja", "meeting room"],
            "type": "semi_public",
            "notes": "jam kerja, ada CCTV"
        },
        "hotel": {
            "keywords": ["hotel", "penginapan", "inn", "lodging"],
            "type": "private",
            "notes": "netral, aman untuk berduaan"
        },
        "mobil": {
            "keywords": ["mobil", "car", "mobil mas", "parkiran"],
            "type": "semi_private",
            "notes": "ruang terbatas, bisa ketahuan orang lewat"
        },
    }
    
    @classmethod
    def detect_location_from_text(cls, text: str):
        """Deteksi lokasi dari teks user."""
        from core.state_models import LocationContext
        
        text_lower = text.lower()
        
        for loc_id, info in cls.LOCATION_KEYWORDS.items():
            if any(kw in text_lower for kw in info["keywords"]):
                return LocationContext(
                    name=loc_id.replace("_", " ").title(),
                    type=info["type"],
                    owner=info.get("owner"),
                    notes=info.get("notes"),
                )
        
        if "kamar" in text_lower:
            if "kamar mas" in text_lower or "kamarku" in text_lower:
                return LocationContext(name="Kamar Mas", type="private", owner="Mas")
            elif "kamar dietha" in text_lower:
                return LocationContext(name="Kamar Dietha", type="private", owner="Dietha")
            else:
                return LocationContext(name="Kamar", type="private", owner="tidak jelas")
        
        return None
    
    @classmethod
    def update_location_from_text(cls, role_state, user_text: str) -> bool:
        """Update lokasi berdasarkan teks user. Return True jika berubah."""
        from core.state_models import LocationContext
        
        new_location = cls.detect_location_from_text(user_text)
        if not new_location:
            return False
        
        if role_state.current_location:
            if role_state.current_location.name == new_location.name:
                return False
        
        role_state.set_location(new_location)
        return True
