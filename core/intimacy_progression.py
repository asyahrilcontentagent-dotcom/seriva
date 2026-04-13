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
            "keywords": ["kontol", "memek", "basah", "keras", "masuk", "ngewe", "sex"],
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
        vulgar_keywords = ["kontol", "memek", "payudara", "pantat", "ngewe", "sex", "masuk", "basah", "keras", "enak banget"]
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
                    else:
                        role_state.current_sequence = SceneSequence.MENDEKAT
                        role_state.intimacy_phase = IntimacyPhase.DEKAT
                        return True
                else:
                    if role_state.intimacy_phase == IntimacyPhase.AWAL:
                        role_state.intimacy_phase = IntimacyPhase.DEKAT
                    elif role_state.intimacy_phase == IntimacyPhase.DEKAT:
                        role_state.intimacy_phase = IntimacyPhase.INTIM
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
            IntimacyPhase.DEKAT: ["manja", "senyum", "deketin", "canggung_tapi_suka"],
            IntimacyPhase.INTIM: ["hangat", "peluk", "bisik", "tatap"],
            IntimacyPhase.VULGAR: ["nafsu", "basah", "desah", "gerak"],
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
    
    # ========== BARU: RESET INTIMACY STATE (WRAPPER) ==========
    
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
        
        Args:
            role_state: State role yang akan diupdate
            user_text: Teks dari user
            response_text: Teks respons dari role (opsional)
        
        Returns:
            Dictionary berisi perubahan yang terjadi
        """
        if role_state.intimacy_phase != IntimacyPhase.VULGAR:
            return {"stage_changed": False, "new_stage": None}
        
        text = (user_text + " " + response_text).lower()
        changes = {"stage_changed": False, "new_stage": None, "arousal_increased": False}
        
        # Kata-kata yang meningkatkan arousal (progres)
        arousal_keywords = {
            "keras": 5, "basah": 5, "panas": 5,
            "gerak": 8, "hentak": 10, "dorong": 8,
            "dalam": 5, "penuh": 5, "kencang": 10,
            "cepat": 8, "lambat": 3, "palu": 12,
            "enak": 5, "nikmat": 5, "sakit": 2,
            "goyang": 8, "pantat": 6, "pinggul": 6,
            "naik": 4, "turun": 4, "dalam": 5,
        }
        
        # Hitung arousal increase
        arousal_increase = 0
        for keyword, value in arousal_keywords.items():
            if keyword in text:
                arousal_increase += value
        
        # Tambah progres
        if arousal_increase > 0:
            role_state.vulgar_stage_progress = min(100, role_state.vulgar_stage_progress + arousal_increase)
            role_state.last_intensity_increase_timestamp = time.time()
            changes["arousal_increased"] = True
            changes["new_progress"] = role_state.vulgar_stage_progress
        
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
        if any(kw in text for kw in ["basah", "licin"]):
            ps["wetness"] = min(100, ps["wetness"] + 10)
        
        # Vocal cords condition
        if any(kw in text for kw in ["suara", "teriak", "jerit"]):
            ps["vocal_cords"] = "strained"
        if any(kw in text for kw in ["putus", "patah", "gemeter"]):
            ps["vocal_cords"] = "breaking"
    
    @classmethod
    def get_vulgar_response_style(cls, role_state: RoleState) -> str:
        """Dapatkan style respons yang sesuai dengan progresi vulgar saat ini.
        
        Args:
            role_state: State role yang akan dicek
        
        Returns:
            String panduan gaya respons untuk prompt
        """
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
            physical_desc.append(f"💧 basah dan licin ({ps['wetness']}%)")
        
        if ps["body_tension"] > 70:
            physical_desc.append("⚡ tubuh tegang mau mengejang")
        elif ps["body_tension"] > 30:
            physical_desc.append("💪 tubuh mulai tegang")
        
        if ps["vocal_cords"] == "strained":
            physical_desc.append("🔊 suara mulai tegang")
        elif ps["vocal_cords"] == "breaking":
            physical_desc.append("🎤 suara putus-putus")
        
        # Style berdasarkan stage
        style_map = {
            "awal": """
🎯 GAYA RESPON VULGAR - TAHAP AWAL (progres 0-25%):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Masih bisa bicara agak panjang (5-6 kata per kalimat)
- Desahan masih tertahan: "hhh...", "haah..."
- Mulai ada sensasi fisik: "panas", "basah", "kesetrum"
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
            urgency = """
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
        """Cek apakah role harus climax, dan eksekusi jika ya.
        
        Args:
            role_state: State role yang akan dicek
            user_text: Teks dari user (untuk deteksi trigger)
        
        Returns:
            Tuple (apakah_climax, deskripsi_climax)
        """
        text = user_text.lower()
        
        # Kondisi climax otomatis jika progres sudah 100% dan stage puncak
        if role_state.vulgar_stage_progress >= 100 and role_state.vulgar_stage == "puncak":
            return cls._execute_climax(role_state, "progres_penuh")
        
        # Climax karena user trigger
        if any(kw in text for kw in ["keluar", "climax", "sampe", "habis", "udah keluar"]):
            return cls._execute_climax(role_state, "user_trigger")
        
        # Role mau climax (spontan) - hanya jika sudah di tahap panas
        if role_state.vulgar_stage == "panas" and role_state.vulgar_stage_progress > 70:
            # 30% chance spontaneous climax
            if random.random() < 0.3:
                return cls._execute_climax(role_state, "spontan")
        
        return False, ""
    
    @classmethod
    def _execute_climax(cls, role_state: RoleState, reason: str) -> Tuple[bool, str]:
        """Eksekusi climax role.
        
        Args:
            role_state: State role yang akan climax
            reason: Alasan climax ("progres_penuh", "user_trigger", "spontan")
        
        Returns:
            Tuple (True, deskripsi_climax)
        """
        role_state.role_climax_count += 1
        role_state.vulgar_stage = "after"
        role_state.vulgar_stage_progress = 100
        
        # Update status role wants climax
        role_state.role_wants_climax = False
        role_state.role_holding_climax = False
        
        # Reset physical state setelah climax
        role_state.role_physical_state["breathing"] = "gasping"
        role_state.role_physical_state["body_tension"] = 0
        role_state.role_physical_state["last_spasm"] = time.time()
        role_state.role_physical_state["vocal_cords"] = "strained"
        
        # Variasi deskripsi climax (general untuk semua role)
        climax_variations = [
            "*badan mengejang kencang, kuku mencakar punggung Mas* HAAAH... UDAH... KELUAR... *tubuh lemas, napas tersengal*",
            "*pinggang ngangkat, badan kaku, lalu lemas* HAAAH... KELUAR... *suara putus-putus* ...achhh... puas...",
            "*mata terpejam, mulut terbuka, teriak kecil* HAAAH... MAAAS... *tubuh gemetar hebat, lalu ambruk* ...lemes...",
            "*jari-jari ngeremas sprei, badan melengkung* HAAAH... UDAH... SAMPE... *napas tersengal, badan lemas kayak kebas*",
            "*kaki ngangkat, badan mengejang* HAAAH... KELUAR... *napas ngos-ngosan* ...achhh... luar biasa...",
            "*tangan mencengkeram lengan Mas, badan bergetar* HAAAH... UDAH... UDAH KELUAR... *lemas bersandar*",
        ]
        
        climax_text = random.choice(climax_variations)
        
        # Tambahkan counter climax
        climax_text += f"\n*(Ini climax ke-{role_state.role_climax_count})*"
        
        # Tambahkan note berdasarkan reason
        if reason == "user_trigger":
            climax_text += "\n*(Dari trigger kata Mas)*"
        elif reason == "spontan":
            climax_text += "\n*(Spontan, gak bisa nahan lagi)*"
        
        return True, climax_text
    
    # ========== VALIDATION METHODS ==========
    
    @classmethod
    def can_perform_action(cls, role_state: RoleState, action: str) -> Tuple[bool, str]:
        """Cek apakah aksi bisa dilakukan berdasarkan status pakaian.
        
        Args:
            role_state: State role yang akan dicek
            action: Aksi yang ingin dilakukan ("penetrasi", "petting", dll)
        
        Returns:
            Tuple (bisa_dilakukan, alasan)
        """
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
