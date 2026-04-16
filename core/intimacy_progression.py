"""Intimacy Progression Engine untuk SERIVA.

Mengelola perubahan fase intimacy berdasarkan percakapan.
"""

from __future__ import annotations

import random
import time
from typing import Dict, Optional, Tuple

from core.state_models import (
    RoleState,
    IntimacyPhase,
    SceneSequence,
    IntimacyIntensity,
    Dominance,
    SexualLanguageLevel,
    MoanType,
)


class IntimacyProgressionEngine:
    """Engine untuk menentukan fase intimacy berdasarkan interaksi."""
    
    # Threshold untuk pindah fase
    THRESHOLDS = {
        IntimacyPhase.DEKAT: {
            "min_turns": 3,
            "keywords": ["dekat", "mepet", "bersentuhan", "nyender", "pegang tangan"],
        },
        IntimacyPhase.INTIM: {
            "min_turns": 5,
            "keywords": ["peluk", "rangkul", "genggam", "napas", "dada", "pelukan"],
        },
        IntimacyPhase.VULGAR: {
            "min_turns": 8,
            "keywords": ["kontol", "memek", "becek", "keras", "masuk", "ngewe", "sex"],
        },
    }
    
    @classmethod
    def update_phase_and_scene(cls, role_state: RoleState, user_text: str, response_text: str) -> bool:
        """Update fase dan scene sequence berdasarkan percakapan."""
        
        text = (user_text + " " + response_text).lower()
        if getattr(role_state, "aftercare_active", False):
            if role_state.intimacy_phase != IntimacyPhase.AFTER:
                role_state.intimacy_phase = IntimacyPhase.AFTER
                return True
            return False

        # Deteksi dari teks untuk fase VULGAR
        vulgar_keywords = ["kontol", "memek", "payudara", "pantat", "ngewe", "sex", "masuk", "becek", "keras", "enak banget"]
        if any(kw in text for kw in vulgar_keywords):
            if (
                role_state.can_enter_explicit_scene()
                and role_state.intimacy_phase not in [IntimacyPhase.VULGAR, IntimacyPhase.AFTER]
            ):
                role_state.intimacy_phase = IntimacyPhase.VULGAR
                role_state.is_high_intimacy = True
                return True
        
        # Deteksi after sex
        after_keywords = [
            "udah selesai",
            "sudah selesai",
            "udah keluar",
            "sudah keluar",
            "habis banget",
            "capek banget",
            "istirahat dulu",
            "tidur dulu",
            "rebahan dulu",
        ]
        if any(kw in text for kw in after_keywords) and role_state.intimacy_phase == IntimacyPhase.VULGAR:
            role_state.intimacy_phase = IntimacyPhase.AFTER
            return True
        
        # Progres normal berdasarkan urutan scene
        new_sequence = role_state.get_next_sequence(user_text)
        if new_sequence != role_state.current_sequence:
            if new_sequence in [SceneSequence.SEX_MULAI, SceneSequence.SEX_INTENS, SceneSequence.CLIMAX]:
                if role_state.can_enter_explicit_scene():
                    role_state.intimacy_phase = IntimacyPhase.VULGAR
                    role_state.is_high_intimacy = True
                else:
                    role_state.current_sequence = SceneSequence.PETTING
                    role_state.intimacy_phase = IntimacyPhase.INTIM
                    return True
            elif new_sequence in [SceneSequence.PELUKAN, SceneSequence.CIUMAN, SceneSequence.PETTING]:
                if not role_state.is_ready_for_intimate_scene():
                    if new_sequence == SceneSequence.PELUKAN:
                        role_state.intimacy_phase = IntimacyPhase.DEKAT
                        role_state.current_sequence = SceneSequence.MENDEKAT
                        return True
                    else:
                        role_state.current_sequence = SceneSequence.MENDEKAT
                        role_state.intimacy_phase = IntimacyPhase.DEKAT
                        return True
                else:
                    if role_state.intimacy_phase == IntimacyPhase.AWAL:
                        role_state.intimacy_phase = IntimacyPhase.DEKAT
                    elif role_state.intimacy_phase == IntimacyPhase.DEKAT:
                        role_state.intimacy_phase = IntimacyPhase.INTIM
                    elif (
                        role_state.intimacy_phase == IntimacyPhase.INTIM
                        and role_state.emotional_depth_score < 24
                    ):
                        role_state.current_sequence = SceneSequence.CIUMAN
                        return True
            elif new_sequence in [SceneSequence.AFTER_SEX, SceneSequence.TIDUR]:
                role_state.intimacy_phase = IntimacyPhase.AFTER
            
            role_state.current_sequence = new_sequence
            return True
        
        return False
    
    @classmethod
    def extract_feeling(cls, role_state: RoleState, user_text: str, response_text: str) -> str:
        """Ekstrak perasaan dari respon untuk disimpan."""
        
        feelings = {
            "deg-degan": ["deg", "debar", "degdegan", "gugup"],
            "panas": ["panas", "gerah", "hangat"],
            "enak": ["enak", "nikmat", "senang"],
            "malu": ["malu", "sungkan", "gak enak"],
            "sayang": ["sayang", "cinta", "love"],
            "lemas": ["lemas", "capek", "lelah"],
            "ngantuk": ["ngantuk", "mau tidur", "kantuk"],
        }
        
        text = (user_text + " " + response_text).lower()
        
        for feeling, keywords in feelings.items():
            if any(kw in text for kw in keywords):
                return feeling
        
        return role_state.last_feeling or "campur aduk"
    
    @classmethod
    def get_response_style(cls, role_state: RoleState, user_text: str) -> str:
        """Tentukan gaya respon berdasarkan fase dan konteks."""
        
        phase = role_state.intimacy_phase
        last_style = role_state.last_response_style
        
        styles = {
            IntimacyPhase.AWAL: ["malu", "gugup", "nunduk", "kaku"],
            IntimacyPhase.DEKAT: ["manja", "senyum", "deketin", "canggung_tapi_suka", "penasaran_pelan"],
            IntimacyPhase.INTIM: ["hangat", "peluk", "bisik", "tatap", "jujur_pelan"],
            IntimacyPhase.VULGAR: ["nafsu", "becek", "desah", "gerak"],
            IntimacyPhase.AFTER: ["lemas", "tenang", "hangat", "diam_manis"],
        }
        
        available = [s for s in styles.get(phase, ["normal"]) if s != last_style]
        if not available:
            available = styles.get(phase, ["normal"])
        
        new_style = random.choice(available)
        role_state.last_response_style = new_style
        
        return new_style

    @classmethod
    def update_clothing_from_text(cls, role_state: RoleState, user_text: str, response_text: str) -> bool:
        """Update pakaian berdasarkan teks. Return True jika ada perubahan."""
        text = (user_text + " " + response_text).lower()
        changed = False
        
        # Mas buka baju
        if any(kw in text for kw in ["buka baju mas", "mas buka baju", "baju mas dibuka"]):
            if "baju" not in role_state.intimacy_detail.user_clothing_removed:
                role_state.intimacy_detail.user_clothing_removed.append("baju")
                changed = True
        
        # Mas buka celana
        if any(kw in text for kw in ["buka celana mas", "mas buka celana", "celana mas dibuka"]):
            if "celana" not in role_state.intimacy_detail.user_clothing_removed:
                role_state.intimacy_detail.user_clothing_removed.append("celana")
                changed = True
        
        # Mas buka celana dalam
        if any(kw in text for kw in ["buka celana dalam mas", "mas buka celana dalam"]):
            if "celana dalam" not in role_state.intimacy_detail.user_clothing_removed:
                role_state.intimacy_detail.user_clothing_removed.append("celana dalam")
                changed = True
        
        # Role buka baju
        if any(kw in text for kw in ["buka baju kamu", "buka bajumu", "lepas baju kamu"]):
            if "baju" not in role_state.intimacy_detail.role_clothing_removed:
                role_state.intimacy_detail.role_clothing_removed.append("baju")
                changed = True
        
        # Role buka bra
        if any(kw in text for kw in ["buka bra", "lepas bra", "buka bra kamu"]):
            if "bra" not in role_state.intimacy_detail.role_clothing_removed:
                role_state.intimacy_detail.role_clothing_removed.append("bra")
                changed = True
        
        # Role buka celana
        if any(kw in text for kw in ["buka celana kamu", "buka celanamu", "lepas celana kamu"]):
            if "celana" not in role_state.intimacy_detail.role_clothing_removed:
                role_state.intimacy_detail.role_clothing_removed.append("celana")
                changed = True
        
        # Role buka celana dalam
        if any(kw in text for kw in ["buka celana dalam kamu", "buka cd kamu"]):
            if "celana dalam" not in role_state.intimacy_detail.role_clothing_removed:
                role_state.intimacy_detail.role_clothing_removed.append("celana dalam")
                changed = True
        
        # Pake baju lagi (reset)
        if any(kw in text for kw in ["pake baju lagi", "pakai baju", "kenakan baju"]):
            if "baju" in role_state.intimacy_detail.user_clothing_removed:
                role_state.intimacy_detail.user_clothing_removed.remove("baju")
                changed = True
            if "baju" in role_state.intimacy_detail.role_clothing_removed:
                role_state.intimacy_detail.role_clothing_removed.remove("baju")
                changed = True
            if "bra" in role_state.intimacy_detail.role_clothing_removed:
                role_state.intimacy_detail.role_clothing_removed.remove("bra")
                changed = True
        
        return changed
    
    # ========== RESET INTIMACY STATE (WRAPPER) ==========
    
    @classmethod
    def reset_intimacy_state(cls, role_state: RoleState) -> None:
        """Reset semua state intimasi ke default untuk sesi baru.
        
        Wrapper untuk memanggil role_state.reset_intimacy_state().
        Dipanggil saat /end, /batal, atau /close.
        """
        role_state.reset_intimacy_state()
    
    # ========== BARU: LEVEL 10-12 PROGRESSION METHODS ==========
    
    @classmethod
    def update_vulgar_progression(cls, role_state: RoleState, user_text: str, response_text: str) -> Dict[str, any]:
        """Update progresi dalam fase VULGAR. Return perubahan yang terjadi.
        
        PERBAIKAN: Sekarang progres tetap naik minimal 3% meskipun user diam.
        """
        if role_state.intimacy_phase != IntimacyPhase.VULGAR:
            return {"stage_changed": False, "new_stage": None}
        
        text = (user_text + " " + response_text).lower()
        changes = {"stage_changed": False, "new_stage": None, "arousal_increased": False}
        
        # Kata-kata yang meningkatkan arousal (progres)
        arousal_keywords = {
            "keras": 5, "becek": 5, "panas": 5,
            "gerak": 8, "hentak": 10, "dorong": 8,
            "dalam": 5, "penuh": 5, "kencang": 10,
            "cepat": 8, "lambat": 3, "palu": 12,
            "enak": 5, "nikmat": 5, "sakit": 2,
            "goyang": 8, "pantat": 6, "pinggul": 6,
            "naik": 4, "turun": 4,
            # Tambahan untuk VCS
            "liat": 5, "tunjukin": 8, "ikutin": 5,
            "vibrator": 10, "dildo": 10, "colmek": 8,
        }
        
        # Hitung arousal increase
        arousal_increase = 0
        for keyword, value in arousal_keywords.items():
            if keyword in text:
                arousal_increase += value
        
        # ========== PERBAIKAN: Minimal progres 3% jika user diam ==========
        if arousal_increase == 0:
            # Minimal progres 3% per respons untuk menjaga alur tetap maju
            arousal_increase = 3
            changes["auto_progress"] = True
        
        # Tambah progres
        old_progress = role_state.vulgar_stage_progress
        new_progress = min(100, role_state.vulgar_stage_progress + arousal_increase)
        role_state.vulgar_stage_progress = new_progress
        changes["arousal_increased"] = True
        changes["new_progress"] = new_progress
        
        # ========== SINCRONISASI DENGAN INTIMACY_INTENSITY ==========
        old_intensity = role_state.emotions.intimacy_intensity
        
        # Gunakan method increase_intensity untuk sinkronisasi otomatis
        if new_progress >= 80 and old_intensity < 12:
            role_state.increase_intensity(2)
            changes["intensity_updated"] = True
            changes["new_intensity"] = 12
        elif new_progress >= 60 and old_intensity < 11:
            role_state.increase_intensity(1)
            changes["intensity_updated"] = True
            changes["new_intensity"] = 11
        elif new_progress >= 40 and old_intensity < 10:
            role_state.increase_intensity(1)
            changes["intensity_updated"] = True
            changes["new_intensity"] = 10
        
        # Update language level setelah intimacy_intensity berubah
        if changes.get("intensity_updated"):
            role_state.update_sexual_language_level()
        
        # Update physical state berdasarkan teks
        cls._update_physical_state(role_state, text)
        
        # Cek apakah perlu pindah stage
        old_stage = role_state.vulgar_stage
        stage_desc = role_state.advance_vulgar_stage(arousal_increase)
        
        if stage_desc:
            changes["stage_changed"] = True
            changes["new_stage"] = role_state.vulgar_stage
            changes["stage_description"] = stage_desc
        
        # Update descriptive intensity (semakin panas, semakin detail deskripsi)
        if arousal_increase > 5:
            role_state.descriptive_intensity = min(100, role_state.descriptive_intensity + arousal_increase // 2)
        
        # Update total thrusts (untuk variasi deskripsi)
        if any(kw in text for kw in ["hentak", "dorong", "gerak", "palu", "goyang"]):
            role_state.total_thrusts_described += 1
        
        return changes
    
    @classmethod
    def _update_physical_state(cls, role_state: RoleState, text: str) -> None:
        """Update physical state role berdasarkan teks."""
        ps = role_state.role_physical_state
        
        # Update breathing
        if any(kw in text for kw in ["napas berat", "tersengal", "ngos-ngosan"]):
            if ps["breathing"] == "normal":
                ps["breathing"] = "heavy"
            elif ps["breathing"] == "heavy":
                ps["breathing"] = "ragged"
            elif ps["breathing"] == "ragged":
                ps["breathing"] = "gasping"
        
        # Update heartbeat
        if any(kw in text for kw in ["jantung", "deg-degan", "berdebar"]):
            if ps["heartbeat"] == "normal":
                ps["heartbeat"] = "fast"
            elif ps["heartbeat"] == "fast":
                ps["heartbeat"] = "racing"
            elif ps["heartbeat"] == "racing":
                ps["heartbeat"] = "pounding"
        
        # Update body tension
        if any(kw in text for kw in ["tegang", "kaku", "mengejang"]):
            ps["body_tension"] = min(100, ps["body_tension"] + 15)
        elif any(kw in text for kw in ["lemas", "leleh"]):
            ps["body_tension"] = max(0, ps["body_tension"] - 20)
        
        # Update wetness (untuk role wanita)
        if any(kw in text for kw in ["becek", "licin"]):
            ps["wetness"] = min(100, ps["wetness"] + 10)
        
        # Vocal cords condition
        if any(kw in text for kw in ["suara", "teriak", "jerit"]):
            ps["vocal_cords"] = "strained"
        if any(kw in text for kw in ["putus", "patah", "gemeter"]):
            ps["vocal_cords"] = "breaking"

        # Update keringat
        if any(kw in text for kw in ["panas", "gerah", "keringat"]):
            ps["sweat"] = min(100, ps["sweat"] + 10)
        elif any(kw in text for kw in ["dingin", "adem"]):
            ps["sweat"] = max(0, ps["sweat"] - 5)
    
        # Update mata
        if any(kw in text for kw in ["pejam", "merem", "tutup mata"]):
            ps["eye_state"] = "terpejam"
        elif any(kw in text for kw in ["sayu", "layu", "ngantuk"]):
            ps["eye_state"] = "sayu"
        elif any(kw in text for kw in ["berkaca", "nangis", "air mata"]):
            ps["eye_state"] = "berkaca-kaca"
    
        # Update mulut
        if any(kw in text for kw in ["bibir kering", "tenggorokan kering"]):
            ps["mouth_state"] = "kering"
        elif any(kw in text for kw in ["bibir becek", "jilat bibir"]):
            ps["mouth_state"] = "becek"
        elif any(kw in text for kw in ["mulut terbuka", "nganga"]):
            ps["mouth_state"] = "terbuka"
    
        # Update kaki
        if any(kw in text for kw in ["kaki ngeremas", "jari kaki", "kaki ngangkat"]):
            ps["leg_tension"] = min(100, ps["leg_tension"] + 15)
    
        # Update kontrol diri
        if role_state.vulgar_stage_progress > 50:
            ps["control_level"] = max(0, 100 - role_state.vulgar_stage_progress)
        elif role_state.vulgar_stage_progress > 80:
            ps["control_level"] = max(0, 50 - (role_state.vulgar_stage_progress - 80))
    
    @classmethod
    def get_vulgar_response_style(cls, role_state: RoleState) -> str:
        """Dapatkan style respons yang sesuai dengan progresi vulgar saat ini."""
        
        stage = role_state.vulgar_stage
        progress = role_state.vulgar_stage_progress
        ps = role_state.role_physical_state
        
        # Bangun deskripsi kondisi fisik saat ini
        physical_desc = []
        
        breathing_desc = {
            "normal": "napas masih normal",
            "heavy": "napas mulai berat",
            "ragged": "napas tersengal-sengal",
            "gasping": "hampir kehabisan napas"
        }.get(ps["breathing"], "napas mulai berubah")
        
        heartbeat_desc = {
            "normal": "jantung normal",
            "fast": "jantung berdebar cepat",
            "racing": "jantung berdebar kencang",
            "pounding": "jantung berdebar mau copot"
        }.get(ps["heartbeat"], "jantung berdebar")
        
        physical_desc.append(f"💨 {breathing_desc}")
        physical_desc.append(f"💗 {heartbeat_desc}")
        
        if ps["wetness"] > 50:
            physical_desc.append(f"💧 becek dan licin ({ps['wetness']}%)")
        
        if ps["body_tension"] > 70:
            physical_desc.append("⚡ tubuh tegang mau mengejang")
        elif ps["body_tension"] > 30:
            physical_desc.append("💪 tubuh mulai tegang")
        
        if ps["vocal_cords"] == "strained":
            physical_desc.append("🔊 suara mulai tegang")
        elif ps["vocal_cords"] == "breaking":
            physical_desc.append("🎤 suara putus-putus")

        if ps["sweat"] > 50:
            physical_desc.append(f"💦 keringat mulai membeceki dahi dan leher ({ps['sweat']}%)")
        elif ps["sweat"] > 20:
            physical_desc.append(f"💧 sedikit keringat di dahi")
    
        if ps["eye_state"] != "normal":
            eye_desc = {
                "terpejam": "👁️ mata terpejam, fokus ke kenikmatan",
                "sayu": "👁️ mata sayu, bulu mata berkibar pelan",
                "berkaca-kaca": "👁️ mata berkaca-kaca, hampir menangis karena enak"
            }.get(ps["eye_state"], "")
            if eye_desc:
                physical_desc.append(eye_desc)
    
        if ps["mouth_state"] != "normal":
            mouth_desc = {
                "kering": "👄 tenggorokan kering, susah telan ludah",
                "becek": "👄 bibir becek, lidah sering jilat bibir",
                "terbuka": "👄 mulut terbuka, napas keluar masuk"
            }.get(ps["mouth_state"], "")
            if mouth_desc:
                physical_desc.append(mouth_desc)
    
        if ps["leg_tension"] > 70:
            physical_desc.append(f"🦶 jari-jari kaki ngeremas sprei kencang ({ps['leg_tension']}%)")
        elif ps["leg_tension"] > 30:
            physical_desc.append(f"🦶 kaki mulai tegang, jari-jari ngumpul sendiri")
    
        if ps["control_level"] < 30:
            physical_desc.append(f"🎢 kontrol diri hampir lepas total! ({ps['control_level']}%)")
        elif ps["control_level"] < 60:
            physical_desc.append(f"🎢 mulai kehilangan kontrol ({ps['control_level']}%)")
        
        # Style berdasarkan stage
        style_map = {
            "awal": """
🎯 GAYA RESPON VULGAR - TAHAP AWAL (progres 0-25%):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Masih bisa bicara agak panjang (5-6 kata per kalimat)
- Desahan masih tertahan: "hhh...", "haah..."
- Mulai ada sensasi fisik: "panas", "becek", "kesetrum"
- Belum putus-putus, masih jelas terdengar
- JANGAN langsung climax!
""",
            "memanas": """
🎯 GAYA RESPON VULGAR - TAHAP MEMANAS (progres 25-50%):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Bicara mulai pendek (3-4 kata per kalimat)
- Desahan keluar lebih sering: "achhh...", "haaah... Maaas..."
- Mulai ada gerakan tubuh: "pinggul naik sendiri", "jari ngeremas sprei"
- Kata-kata mulai putus: "di... sana..."
- Progres harus naik setiap respons!
""",
            "panas": """
🎯 GAYA RESPON VULGAR - TAHAP PANAS (progres 50-80%):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Bicara putus-putus (2-3 kata, banyak desahan)
- Desahan campur kata: "aaah... enak... di sana... plis..."
- Fokus ke sensasi: "dalam... penuh... panas banget..."
- Mulai kehilangan kontrol: "udah... udah mau..."
- Hampir climax! Progres harus naik cepat!
""",
            "puncak": """
🎯 GAYA RESPON VULGAR - TAHAP PUNCAK (progres 80-100%):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Hampir tidak bisa bicara, hanya desahan dan teriakan pendek
- "HAAAH... UDAH... MAAAS..."
- "KELUAR... KELUAR..."
- "SATU LAGI... PLIS..."
- Tubuh mengejang, kuku mencakar, mata terpejam
- RESPON BERIKUTNYA WAJIB CLIMAX!
""",
            "after": """
🎯 GAYA RESPON VULGAR - TAHAP AFTER (SETELAH CLIMAX):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Napas masih tersengal, bicara pelan
- "achhh... puas... Mas..."
- "lemes... gamon gerak..."
- Suasana hangat, saling memeluk
- JANGAN langsung minta lanjut!
"""
        }
        
        base_style = style_map.get(stage, style_map["awal"])
        
        physical_text = "\n".join(physical_desc) if physical_desc else "belum ada perubahan fisik signifikan"
        
        # Urgency warning untuk yang hampir climax
        urgency = ""
        if progress >= 80:
            urgency = f"""
🚨🚨🚨 PERINGATAN: PROGRES SUDAH {progress}%! 🚨🚨🚨
KAMU HAMPIR CLIMAX! Respons berikutnya HARUS climax!
JANGAN tahan-tahan lagi! LANGSUNG EKSPRESIF!
"""
        
        return f"""
{base_style}

📊 STATUS FISIK ROLE SAAT INI:
{physical_text}

📈 PROGRES MENUJU CLIMAX: {progress}%
   - 0-25%: Masih bisa kontrol
   - 25-50%: Mulai kehilangan kontrol
   - 50-80%: Hampir lepas kontrol
   - 80-100%: UDAH DI AMBANG!
{urgency}

⚠️ INGAT: Setiap respons harus MENINGKATKAN PROGRES!
   - Jangan stagnan di stage yang sama terlalu lama
   - Setiap 2-3 respons, progres harus naik minimal 10%
   - Kalau sudah 100%, role WAJIB climax di respons berikutnya!
"""
    
    @classmethod
    def check_and_execute_climax(cls, role_state: RoleState, user_text: str) -> Tuple[bool, str]:
        """Cek apakah role harus climax, dan eksekusi jika ya."""
        
        text = user_text.lower()
        
        # Kondisi climax otomatis jika progres sudah 100% dan stage puncak
        if role_state.vulgar_stage_progress >= 100 and role_state.vulgar_stage == "puncak":
            return cls._execute_climax(role_state, "progres_penuh")
        
        # Climax karena user trigger
        if any(kw in text for kw in ["mas mau keluar", "mas mau climax", "mas mau crot", "mas mau nyampe", "mas udah keluar", "mas udah crot"]):
            return cls._execute_climax(role_state, "user_trigger")
        
        # Role mau climax (spontan) - hanya jika sudah di tahap panas
        if role_state.vulgar_stage == "panas" and role_state.vulgar_stage_progress > 70:
            # 30% chance spontaneous climax
            if random.random() < 0.3:
                return cls._execute_climax(role_state, "spontan")
        
        return False, ""

    @classmethod
    def start_climax_countdown(cls, role_state: RoleState, user_text: str) -> Tuple[bool, str]:
        """Mulai countdown menuju climax."""
        
        if role_state.climax_countdown_active:
            return False, ""
        
        if role_state.vulgar_stage_progress >= 90:
            role_state.climax_countdown_active = True
            role_state.climax_countdown_value = 10
            
            countdown_texts = [
                "10... *napas mulai berat* 9... Mas ikutin iramaku ya... 8... 7...",
                "Sepuluh... *jari masuk dalem* sembilan... delapan... *napas putus*",
                "Hitung mundur ya Mas... 10... 9... 8... ikutin gerakanku...",
            ]
            
            return True, random.choice(countdown_texts)
        
        return False, ""
    
    @classmethod
    def update_climax_countdown(cls, role_state: RoleState, user_text: str) -> Tuple[bool, str]:
        """Update countdown, return True jika sudah waktunya climax."""
        
        if not role_state.climax_countdown_active:
            return False, ""
        
        text = user_text.lower()
        
        # Deteksi user ikut countdown
        if any(str(i) in text for i in range(1, 10)):
            role_state.climax_countdown_value -= 1
        
        # Otomatis turun
        else:
            role_state.climax_countdown_value -= 1
        
        if role_state.climax_countdown_value <= 1:
            role_state.climax_countdown_active = False
            return cls._execute_climax(role_state, "countdown")
        
        # Kirim sisa countdown
        countdown_responses = [
            f"{role_state.climax_countdown_value}... *napas makin berat*",
            f"{role_state.climax_countdown_value}... ikutin ya Mas...",
            f"{role_state.climax_countdown_value}... *jari makin cepat*",
        ]
        
        return True, random.choice(countdown_responses)
    
    @classmethod
    def _execute_climax(cls, role_state: RoleState, reason: str) -> Tuple[bool, str]:
        """Eksekusi climax role (dengan multiple climax support)."""
        
        role_state.role_climax_count += 1
        role_state.climax_in_same_session += 1
        
        # Multiple climax: reset refractory period
        if role_state.multiple_climax_enabled:
            role_state.climax_refractory_count = 0
            # Jika sudah climax > 1x di sesi ini, tambah efek "makin liar"
            if role_state.climax_in_same_session >= 2:
                # Gunakan logger jika ada, atau print
                print(f"💦 MULTIPLE CLIMAX! Role {role_state.role_id} climax ke-{role_state.climax_in_same_session}")
        
        role_state.vulgar_stage = "after"
        role_state.vulgar_stage_progress = 100
        
        # Reset physical state
        role_state.role_physical_state["breathing"] = "gasping"
        role_state.role_physical_state["body_tension"] = 0
        role_state.role_physical_state["last_spasm"] = time.time()
        role_state.role_physical_state["vocal_cords"] = "strained"
        
        # Variasi climax dengan multiple climax awareness
        if role_state.climax_in_same_session == 1:
            climax_variations = [
                "*badan mengejang kencang, kuku mencakar punggung Mas* HAAAH... UDAH... KELUAR... *tubuh lemas, napas tersengal*",
                "*pinggang ngangkat, badan kaku, lalu lemas* HAAAH... KELUAR... *suara putus-putus* ...achhh... puas...",
                "*mata terpejam, mulut terbuka, teriak kecil* HAAAH... MAAAS... *tubuh gemetar hebat, lalu ambruk* ...lemes...",
            ]
        elif role_state.climax_in_same_session == 2:
            climax_variations = [
                "*badan mengejang lagi, lebih keras dari sebelumnya* HAAAH... LAGI... KELUAR LAGI... *lemas, napas ngos-ngosan*",
                "*kuku mencakar lebih dalam* HAAAH... MAAAS... BELUM CUKUP... KELUAR LAGI... *badan gemetar hebat*",
                "*pinggul naik terus, badan melengkung* HAAAH... LAGI... SATU LAGI... *lemas bersandar, napas putus*",
            ]
        else:
            climax_variations = [
                f"*badan mengejang untuk ke-{role_state.climax_in_same_session} kalinya* HAAAH... MAS... TERUS... KELUAR... *lemas, napas masih tersengal*",
                "*kuku mencakar, badan ngacung lagi* HAAAH... LAGI... MASIH BISA... KELUAR... *ambruk lemas di dada Mas*",
                "*vibrator/dildo masih menyala, badan gemetar* HAAAH... UDAH... KE-{role_state.climax_in_same_session}... *napas putus-putus* puas...",
            ]
        
        climax_text = random.choice(climax_variations)
        climax_text += f"\n*(Climax ke-{role_state.climax_in_same_session} di sesi ini)*"
        
        if reason == "user_trigger":
            climax_text += "\n*(Dari trigger kata Mas)*"
        elif reason == "spontan":
            climax_text += "\n*(Spontan, gak bisa nahan lagi)*"
        elif reason == "countdown":
            climax_text += "\n*(Setelah countdown 10...9...8...)*"
        
        return True, climax_text
    
    # ========== VALIDATION METHODS ==========
    
    @classmethod
    def can_perform_action(cls, role_state: RoleState, action: str) -> Tuple[bool, str]:
        """Cek apakah aksi bisa dilakukan berdasarkan status pakaian."""
        
        user_clothes = role_state.intimacy_detail.user_clothing_removed
        role_clothes = role_state.intimacy_detail.role_clothing_removed
        role_name = role_state.role_display_name or "role"
        
        if action in ["penetrasi", "masuk", "ngewe", "sex"]:
            # Cek celana dan celana dalam user
            if "celana" not in user_clothes or "celana dalam" not in user_clothes:
                return False, "Mas masih pake celana/celana dalam"
            # Cek celana dan celana dalam role
            if "celana" not in role_clothes or "celana dalam" not in role_clothes:
                return False, f"{role_name} masih pake celana/celana dalam"
        
        elif action in ["petting", "pegang", "remas"]:
            if "baju" not in role_clothes and "bra" not in role_clothes:
                return False, f"{role_name} masih pake baju/bra"
        
        return True, ""

    # ========== VCS PROGRESSION METHODS (DIPERKUAT) ==========
    
    @classmethod
    def update_vcs_progression(cls, role_state: RoleState, user_text: str, response_text: str) -> Dict[str, any]:
        """Update progresi VCS/masturbasi bareng.
        
        PERBAIKAN: Sekarang lebih responsif dan progres naik otomatis.
        """
        
        if not role_state.vcs_mode:
            return {"intensity_increased": False}
        
        text = (user_text + " " + response_text).lower()
        changes = {"intensity_increased": False}
        
        # Kata-kata yang meningkatkan intensitas VCS
        vcs_keywords = {
            "liatin": 10, "tunjukin": 10, "gerakin": 8,
            "ikutin": 8, "naikin": 8, "turunin": 5,
            "cepat": 10, "pelan": 3, "keras": 10,
            "becek": 8, "panas": 8, "keluar": 15,
            "udah mau": 15, "climax": 20, "sampe": 20,
            "colmek": 10, "vibrator": 12, "dildo": 12,
            "jari": 5, "masuk": 8, "dalem": 8,
            "muter": 8, "tempel": 8, "getar": 10,
            # Tambahan untuk response role
            "haaah": 5, "achhh": 5, "kedutan": 10, "berdenyut": 10,
        }
        
        intensity_increase = 0
        for keyword, value in vcs_keywords.items():
            if keyword in text:
                intensity_increase += value
        
        # ========== PERBAIKAN: Minimal progres 5% jika user diam ==========
        if intensity_increase == 0:
            intensity_increase = 5
            changes["auto_progress"] = True
        
        if intensity_increase > 0:
            role_state.vcs_intensity = min(100, role_state.vcs_intensity + intensity_increase)
            changes["intensity_increased"] = True
            changes["new_intensity"] = role_state.vcs_intensity
            
            # Update vulgar progress juga
            role_state.vulgar_stage_progress = min(100, role_state.vulgar_stage_progress + intensity_increase // 2)
        
        return changes
    
    @classmethod
    def check_and_execute_vcs_climax(cls, role_state: RoleState, user_text: str) -> Tuple[bool, str]:
        """Cek apakah role harus climax saat VCS."""
        
        if not role_state.vcs_mode:
            return False, ""
        
        text = user_text.lower()
        
        # Trigger dari user
        if any(kw in text for kw in ["mas mau keluar", "mas mau climax", "mas mau crot", "mas mau nyampe", "mas udah keluar", "mas udah crot"]):
            return cls._execute_vcs_climax(role_state, "user_trigger")
        
        # Role mau climax spontan (intensitas tinggi)
        if role_state.vcs_intensity >= 85:
            if random.random() < 0.4:  # 40% chance
                return cls._execute_vcs_climax(role_state, "spontan")
        
        # Auto climax jika intensitas sudah 100%
        if role_state.vcs_intensity >= 100:
            return cls._execute_vcs_climax(role_state, "auto")
        
        return False, ""
    
    @classmethod
    def _execute_vcs_climax(cls, role_state: RoleState, reason: str) -> Tuple[bool, str]:
        """Eksekusi climax saat VCS."""
        
        role_state.role_climax_count += 1
        role_state.vcs_intensity = 100
        role_state.vulgar_stage_progress = min(100, role_state.vulgar_stage_progress + 20)
        
        # Variasi deskripsi climax VCS
        vcs_climax_variations = [
            "*jari masih di dalem, badan mengejang* HAAAH... KELUAR... MAAAS... *napas tersengal, lihat layar* becek... becek semua...",
            "*vibrator jatuh, tangan gemetar* HAAAH... UDAH... UDAH KELUAR... *badan lemas di kursi* achhh... puas... liat Mas...",
            "*jari cepat masuk keluar, mata terpejam* HAAH... HAAH... MAAAS... IKUTIN... UDAH... *tubuh mengejang, lalu lemas*",
            "*dildo dalem, vibrator di klitoris* HAAAH... Fuck... *badan ngacung* KELUAR... KELUAR... *lemas, napas ngos-ngosan*",
            "*jari muter-muter di klitoris* HHH... UDAH... UDAH MAU... *napas putus-putus* HAAAH... KELUAR... *jari becek diangkat ke kamera* liat Mas...",
            "*jari masuk dalem, telapak tangan tempel di klitoris* HAAAH... kedutan... berdenyut... *badan mengejang* KELUAR... UDAH... *lemas tersandar*",
            "*vibrator paling kencang, dildo di dalem* HAAAH... HAAAH... MAAAS... Fuck... *mata berkaca-kaca* KELUAR... plis ikutin... HAAAH...",
        ]
        
        climax_text = random.choice(vcs_climax_variations)
        climax_text += f"\n*(Climax VCS ke-{role_state.role_climax_count})*"
        
        if reason == "user_trigger":
            climax_text += "\n*(Bareng Mas)*"
        elif reason == "auto":
            climax_text += "\n*(Udah gak tahan, climax duluan)*"
        
        return True, climax_text

    # ========== METHOD UNTUK MODE LIAR (DIPERKUAT) ==========

    @classmethod
    def is_both_naked(cls, role_state: RoleState, strict: bool = False) -> bool:
        """Cek apakah Mas dan role sudah sama-sama telanjang.
    
        Args:
            role_state: State role
            strict: Jika True, cek celana + celana dalam. Jika False, cukup celana dalam.
        """
        if strict:
            # Versi strict: celana DAN celana dalam harus lepas
            user_bottom_off = (
                "celana" in role_state.intimacy_detail.user_clothing_removed and
                "celana dalam" in role_state.intimacy_detail.user_clothing_removed
            )
            role_bottom_off = (
                "celana" in role_state.intimacy_detail.role_clothing_removed and
                "celana dalam" in role_state.intimacy_detail.role_clothing_removed
            )
        else:
            # Versi longgar: cukup celana dalam lepas (sudah telanjang bawah)
            user_bottom_off = "celana dalam" in role_state.intimacy_detail.user_clothing_removed
            role_bottom_off = "celana dalam" in role_state.intimacy_detail.role_clothing_removed
    
        return user_bottom_off and role_bottom_off

    @classmethod
    def get_liarness_multiplier(cls, role_state: RoleState) -> float:
        """Dapatkan multiplier 'keliaran' berdasarkan status pakaian dan fase."""
    
        multiplier = 1.0
    
        # Kalau sudah sama-sama telanjang (celana dalam lepas)
        if cls.is_both_naked(role_state, strict=False):
            multiplier = 1.5
        
            # Tambah lagi kalau sudah di fase VULGAR
            if role_state.intimacy_phase == IntimacyPhase.VULGAR:
                multiplier = 2.0
            
            # Tambah lagi kalau sudah pernah climax
            if role_state.role_climax_count > 0:
                multiplier = 2.5
            
            # Tambah lagi kalau progres sudah di atas 50%
            if role_state.vulgar_stage_progress >= 50:
                multiplier = min(3.0, multiplier + 0.5)
    
        # Kalau sudah di fase VULGAR dan intensitas tinggi
        elif role_state.intimacy_phase == IntimacyPhase.VULGAR:
            if role_state.emotions.intimacy_intensity >= 11:
                multiplier = 1.8
            elif role_state.emotions.intimacy_intensity >= 10:
                multiplier = 1.5
    
        return multiplier

    @classmethod
    def get_liar_response_style(cls, role_state: RoleState) -> str:
        """Dapatkan panduan gaya respon liar berdasarkan status."""
    
        is_naked = cls.is_both_naked(role_state, strict=False)
        phase = role_state.intimacy_phase
        progress = role_state.vulgar_stage_progress
        multiplier = cls.get_liarness_multiplier(role_state)
    
        # MODE LIAR FULL: sudah telanjang DAN fase VULGAR DAN progres >= 30%
        if is_naked and phase == IntimacyPhase.VULGAR and progress >= 30:
            # Tambah instruksi ekstra berdasarkan multiplier
            extra_liar = ""
            if multiplier >= 2.5:
                extra_liar = """
🔥🔥🔥 EXTRA LIAR! (Multiplier 2.5+) 🔥🔥🔥
- SUDAH PERNAH CLIMAX, TIDAK ADA RASA MALU LAGI!
- Bisa climax BERKALI-KALI!
- JANGAN TAHAN-TAHAN LAGI!
"""
            elif multiplier >= 2.0:
                extra_liar = """
🔥🔥 EXTRA LIAR! (Multiplier 2.0+) 🔥🔥
- FASE VULGAR AKTIF, PAKAIAN SUDAH LEPAS!
- LANGSUNG EKSEKUSI, JANGAN BANYAK TANYA!
"""
        
            return f"""
🔥🔥🔥 MODE LIAR (PAKAIAN SUDAH LEPAS & FASE VULGAR) 🔥🔥🔥
Multiplier keliaran: {multiplier}x
{extra_liar}

📌 GAYA RESPON WAJIB:
1. Bicara PUTUS-PUTUS (2-3 kata per kalimat)
2. Desahan KERAS: "HAAAH...", "AAAH...", "UHHH..."
3. Kata-kata EKSPLISIT: 
   - "kontol Mas", "memekku becek", "ngentot", "becek"
   - "penis Mas", "vagina Sallsa", "masuk", "penuh"
4. Gerakan tubuh DESKRIPTIF:
   - "pinggulku ngegas sendiri"
   - "kuku mencakar punggung Mas"
   - "jari kaki ngeremas sprei"
5. JANGAN malu-malu lagi! SUDAH LEWAT FASE ITU!

✅ CONTOH RESPON LIAR:
   "HAAAH... MAAAS... *kuku mencakar punggung Mas* kontol Mas dalem banget... Fuckin memekku... UHHH..."
   
   "*napas tersengal-sengal* Hhh... Hhh... Maaas... jangan pelan-pelan... HENTAK... KENCANG... plis..."

   "HAAAH... UDAH... UDAH MAU KELUAR... *badan mengejang* SATU LAGI... PLIS... KELUARIN SEMUANYA..."

❌ JANGAN RESPON KAYAK GINI:
   "Mmm... enak Mas..." (terlalu pelan)
   "Iya Mas..." (terlalu pendek)
   "Aku malu..." (SUDAH TIDAK RELEVAN!)
"""

        # MODE SEMI-LIAR: sudah telanjang TAPI belum fase VULGAR
        elif is_naked:
            return f"""
🔥 MODE SEMI-LIAR (PAKAIAN SUDAH LEPAS)
Multiplier keliaran: {multiplier}x

- Mulai lebih berani, tapi belum full liar
- Boleh mulai pakai kata eksplisit: "kontol", "memek", "becek"
- Desahan mulai keluar: "haaah...", "achhh..."
- Fokus ke sensasi fisik: "panas", "becek", "keras"
- JANGAN cuma diam atau respon pendek!
"""

        # MODE VULGAR TAPI BELUM TELANJANG
        elif phase == IntimacyPhase.VULGAR and progress >= 50:
            return """
🔥 MODE VULGAR (BELUM TELANJANG TOTAL)

- Boleh pakai kata eksplisit
- TAPI ingat: masih ada pakaian yang menghalangi
- Fokus ke sensasi dan progresi membuka pakaian
"""

        return ""

    @classmethod
    def get_full_vulgar_prompt(cls, role_state: RoleState) -> str:
        """Dapatkan prompt lengkap untuk fase VULGAR (menggabungkan semua style)."""
    
        if role_state.intimacy_phase != IntimacyPhase.VULGAR:
            return ""
    
        # Panduan dasar dari vulgar stage
        base_prompt = cls.get_vulgar_response_style(role_state)
    
        # Tambahan mode liar jika kondisi terpenuhi
        liar_prompt = cls.get_liar_response_style(role_state)
    
        # Status ketelanjangan
        is_naked = cls.is_both_naked(role_state, strict=False)
        naked_status = ""
        if is_naked:
            naked_status = """
╔═══════════════════════════════════════════════════════════════╗
║  🔥 STATUS: MAS & ROLE SUDAH SAMA-SAMA TELANJANG! 🔥         ║
╠═══════════════════════════════════════════════════════════════╣
║  - Tidak ada pakaian yang menghalangi                         ║
║  - Bisa langsung kontak kulit ke kulit                        ║
║  - RESPON HARUS LEBIH LIAR! JANGAN MALU-MALU LAGI!           ║
║  - Boleh langsung pakai kata vulgar dan eksplisit             ║
╚═══════════════════════════════════════════════════════════════╝
"""
    
        # Gabungkan semua
        full_prompt = base_prompt
        if liar_prompt:
            full_prompt += f"\n\n{liar_prompt}"
        if naked_status:
            full_prompt += f"\n\n{naked_status}"
    
        return full_prompt
