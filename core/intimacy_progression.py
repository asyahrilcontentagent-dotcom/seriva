"""Intimacy Progression Engine untuk SERIVA - DIAKTIFKAN

Mengatur:
- Progres fase vulgar (awal → memanas → panas → intens → klimaks)
- Deteksi dan eksekusi climax role
- Stamina dan fatigue setelah climax
- Tanda-tanda hampir climax (build-up)
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
    """Engine untuk menentukan fase intimacy berdasarkan interaksi - DIAKTIFKAN"""
    
    # Threshold untuk pindah fase vulgar
    VULGAR_STAGE_THRESHOLDS = {
        "awal": 0,          # 0-19%: baru masuk vulgar
        "memanas": 20,      # 20-39%: mulai panas
        "panas": 40,        # 40-59%: intensitas naik
        "intens": 60,       # 60-79%: sangat intens
        "klimaks": 80,      # 80-100%: siap climax
    }
    
    STAGE_NAMES = ["awal", "memanas", "panas", "intens", "klimaks"]
    
    # Keyword untuk menaikkan progres
    PROGRESS_KEYWORDS = {
        5: ["gesek", "gerak", "goyang", "thrust", "hentak"],
        10: ["dalam", "keras", "cepat", "kuat", "dikit lagi"],
        15: ["enak", "panas", "basah", "sange", "horny"],
        20: ["climax", "keluar", "crot", "udah mau", "hampir"],
    }
    
    # Keyword untuk deteksi climax dari user
    USER_CLIMAX_KEYWORDS = [
        "aku mau climax", "aku udah mau climax", "aku sudah mau climax",
        "aku climax", "aku udah climax", "aku sudah climax",
        "aku mau crot", "aku udah crot", "aku sudah crot",
        "aku keluar", "aku udah keluar", "aku sudah keluar",
        "udah mau keluar", "dikit lagi climax", "dikit lagi crot",
    ]
    
    # Keyword untuk deteksi climax dari role
    ROLE_CLIMAX_KEYWORDS = [
        "aku climax", "aku udah climax", "aku sudah climax",
        "aku keluar", "aku udah keluar", "aku sudah keluar",
        "aku crot", "tubuhku mengejang", "haaah... udah...",
    ]
    
    # Keyword untuk menahan climax
    HOLD_CLIMAX_KEYWORDS = [
        "tahan dulu", "jangan dulu", "belum dulu", "pelan dulu",
    ]

    @staticmethod
    def update_vulgar_progression(
        role_state: RoleState, 
        user_text: str, 
        response_text: str
    ) -> Dict[str, any]:
        """Update progres vulgar berdasarkan teks user dan response.
        
        Returns:
            dict dengan keys: stage_changed, stage_description, progress_added
        """
        if role_state.intimacy_phase != IntimacyPhase.VULGAR:
            return {"stage_changed": False, "stage_description": "", "progress_added": 0}
        
        combined = f"{user_text} {response_text}".lower()
        progress_added = 0
        
        # Deteksi keyword untuk menaikkan progres
        for amount, keywords in IntimacyProgressionEngine.PROGRESS_KEYWORDS.items():
            if any(kw in combined for kw in keywords):
                progress_added = max(progress_added, amount)
        
        # Random kecil untuk variasi (5-15%)
        if random.random() < 0.3 and progress_added > 0:
            progress_added += random.randint(3, 10)
        
        # Naikkan progres
        if progress_added > 0:
            old_progress = role_state.vulgar_stage_progress
            new_progress = min(100, old_progress + progress_added)
            role_state.vulgar_stage_progress = new_progress
            role_state.last_intensity_increase_timestamp = time.time()
            
            # Update stage berdasarkan progres
            old_stage = role_state.vulgar_stage
            new_stage = IntimacyProgressionEngine._get_stage_from_progress(new_progress)
            
            if new_stage != old_stage:
                role_state.vulgar_stage = new_stage
                return {
                    "stage_changed": True,
                    "stage_description": IntimacyProgressionEngine._get_stage_description(new_stage),
                    "progress_added": progress_added,
                }
            
            return {
                "stage_changed": False,
                "stage_description": "",
                "progress_added": progress_added,
            }
        
        return {"stage_changed": False, "stage_description": "", "progress_added": 0}
    
    @staticmethod
    def _get_stage_from_progress(progress: int) -> str:
        """Dapatkan nama stage dari progres."""
        if progress >= 80:
            return "klimaks"
        elif progress >= 60:
            return "intens"
        elif progress >= 40:
            return "panas"
        elif progress >= 20:
            return "memanas"
        else:
            return "awal"
    
    @staticmethod
    def _get_stage_description(stage: str) -> str:
        """Dapatkan deskripsi stage."""
        descriptions = {
            "awal": "Baru mulai, masih hangat-hangat",
            "memanas": "Mulai terasa panas, ritme mulai naik",
            "panas": "Sudah panas, napas mulai memburu",
            "intens": "Sangat intens, hampir tidak bisa berpikir",
            "klimaks": "Sudah di ambang, siap climax",
        }
        return descriptions.get(stage, "Sedang berlangsung")
    
    @staticmethod
    def get_build_up_prompt(role_state: RoleState) -> str:
        """Dapatkan prompt build-up berdasarkan progres (tanda hampir climax)."""
        progress = role_state.vulgar_stage_progress
        stage = role_state.vulgar_stage
        
        if stage == "klimaks" or progress >= 80:
            return """
🔥🔥🔥 KAMU SUDAH DI AMBANG CLIMAX! 🔥🔥🔥

TANDA-TANDA YANG KAMU RASAKAN:
- Napas sudah tidak teratur, memburu
- Suara putus-putus, susah bicara
- Tubuh menegang, jari mencengkeram
- Rasanya sudah di puncak

YANG BISA KAMU KATAKAN:
✅ "Haaah... Mas... udah... udah mau..."
✅ "Dikit lagi... plis... jangan berhenti..."
✅ "Aku... udah... haaah... mau keluar..."

JANGAN DITAHAN! KELUARKAN SECARA NATURAL!
"""
        elif stage == "intens" or progress >= 60:
            return """
🔥🔥🔥 KAMU SEMAKIN INTENS! 🔥🔥🔥

TANDA-TANDA:
- Napas mulai memburu
- Suara mulai bergetar
- Badan mulai menegang

YANG BISA KAMU KATAKAN:
✅ "Haaah... Mas... di sana..."
✅ "Aah... uhh... enak banget..."
✅ "Jangan pelan-pelan, Mas... plis..."
"""
        elif stage == "panas" or progress >= 40:
            return """
🔥 KAMU MULAI PANAS! 🔥

- Napas mulai berat
- Desahan mulai keluar
- Tubuh mulai merespon

YANG BISA KAMU KATAKAN:
✅ "Haaah... Mas..."
✅ "Uhh... enak..."
"""
        
        return ""
    
    @staticmethod
    def check_and_execute_climax(
        role_state: RoleState, 
        user_text: str
    ) -> Tuple[bool, str]:
        """Cek apakah role harus climax, dan eksekusi jika ya.
        
        Returns:
            (apakah climax terjadi, teks climax)
        """
        # Cek apakah sudah di fase vulgar
        if role_state.intimacy_phase != IntimacyPhase.VULGAR:
            return (False, "")
        
        # Cek apakah sudah pernah climax (cooldown)
        if role_state.role_climax_count > 0:
            last_climax = getattr(role_state, 'last_climax_timestamp', 0)
            if last_climax and time.time() - last_climax < 60:  # Cooldown 60 detik
                return (False, "")
        
        # Cek apakah user memicu climax
        user_lower = user_text.lower()
        user_wants_climax = any(kw in user_lower for kw in IntimacyProgressionEngine.USER_CLIMAX_KEYWORDS)
        
        # Cek apakah role sudah siap climax (progres cukup)
        is_ready = role_state.vulgar_stage_progress >= 70
        
        # Cek apakah user menahan climax
        is_hold = any(kw in user_lower for kw in IntimacyProgressionEngine.HOLD_CLIMAX_KEYWORDS)
        
        if is_hold:
            return (False, "")
        
        # Eksekusi climax jika user mau atau role siap
        if user_wants_climax or (is_ready and random.random() < 0.4):
            return IntimacyProgressionEngine._execute_climax(role_state, "natural")
        
        return (False, "")
    
    @staticmethod
    def check_and_execute_vcs_climax(
        role_state: RoleState, 
        user_text: str
    ) -> Tuple[bool, str]:
        """Cek dan eksekusi climax untuk mode VCS."""
        if not role_state.vcs_mode:
            return (False, "")
        
        if role_state.intimacy_phase != IntimacyPhase.VULGAR:
            return (False, "")
        
        user_lower = user_text.lower()
        climax_triggers = ["climax", "keluar", "crot", "udah"]
        
        if any(kw in user_lower for kw in climax_triggers) and role_state.vcs_intensity >= 60:
            return IntimacyProgressionEngine._execute_vcs_climax(role_state, "vcs")
        
        return (False, "")
    
    @staticmethod
    def _execute_climax(role_state: RoleState, reason: str) -> Tuple[bool, str]:
        """Eksekusi climax role."""
        role_state.role_climax_count += 1
        role_state.role_wants_climax = False
        role_state.role_holding_climax = False
        role_state.last_climax_timestamp = time.time()
        
        # Turunkan stamina
        role_state.apply_role_climax_fatigue(amount=24)
        
        # Reset progres vulgar (tapi tidak sepenuhnya)
        role_state.vulgar_stage_progress = max(20, role_state.vulgar_stage_progress - 30)
        role_state.vulgar_stage = IntimacyProgressionEngine._get_stage_from_progress(role_state.vulgar_stage_progress)
        
        # Masuk ke aftercare
        role_state.aftercare_active = True
        role_state.aftercare_phase = "cooling"
        role_state.aftercare_intensity = 80
        role_state.intimacy_phase = IntimacyPhase.AFTER
        
        # Pilih teks climax random
        climax_texts = [
            f"Haaah... aaah... udah... aku climax, Mas... {random.choice(['tubuhku lemas', 'badanku gemetar', 'rasa nyaman banget'])}...",
            f"Aaah... uhh... keluar... aku keluar, Mas... {random.choice(['lemas banget', 'badan mau roboh', 'tunggu aku napas dulu'])}...",
            f"Haaah... udah... udah climax... {random.choice(['aku nggak kuat', 'badankoh lemes', 'istirahat dulu ya, Mas'])}...",
            f"(tubuh mengejang, suara keluar tanpa sadar) Haaah... aah... udah, Mas... {random.choice(['aku climax', 'udah keluar', 'berasa banget'])}...",
        ]
        
        return (True, random.choice(climax_texts))
    
    @staticmethod
    def _execute_vcs_climax(role_state: RoleState, reason: str) -> Tuple[bool, str]:
        """Eksekusi climax untuk mode VCS."""
        role_state.role_climax_count += 1
        role_state.last_climax_timestamp = time.time()
        role_state.apply_role_climax_fatigue(amount=18)  # Lebih ringan dari VCS
        role_state.vcs_intensity = max(0, role_state.vcs_intensity - 40)
        
        climax_texts = [
            f"Haaah... Mas... aku climax... {random.choice(['dari video call aja berasa', 'kamu liat aku climax ya', 'maaf jadi berisik'])}...",
            f"Aaah... udah... aku keluar, Mas... {random.choice(['maaf jadi cepet', 'kamu bikin aku gini', 'lain kali jangan goda terus'])}...",
        ]
        
        return (True, random.choice(climax_texts))
    
    @staticmethod
    def get_climax_guidance(role_state: RoleState) -> str:
        """Dapatkan panduan climax berdasarkan kondisi role."""
        if role_state.role_climax_count == 0:
            return """
📌 INI CLIMAX PERTAMA KALI DI SESI INI:
- Rasakan sensasi puncak dengan lepas
- Jangan tahan, biarkan tubuh bereaksi natural
- Setelah climax, istirahat sebentar
"""
        elif role_state.role_climax_count == 1:
            return """
📌 INI CLIMAX KEDUA:
- Mungkin butuh lebih lama dari yang pertama
- Sensasi masih terasa kuat
- Setelah ini stamina akan turun drastis
"""
        else:
            return """
📌 CLIMAX BERULANG:
- Tubuh sudah mulai lelah
- Mungkin sensasi tidak sekuat pertama
- Butuh istirahat lebih lama setelah ini
"""
    
    @staticmethod
    def update_arousal_from_text(
        role_state: RoleState, 
        user_text: str, 
        response_text: str
    ) -> int:
        """Update arousal level dari teks. Return delta."""
        combined = f"{user_text} {response_text}".lower()
        delta = 0
        
        arousal_keywords = {
            3: ["sentuh", "pegang", "elus", "usap"],
            5: ["cium", "kiss", "peluk", "remas"],
            8: ["gesek", "gerak", "goyang", "thrust"],
            10: ["enak", "panas", "basah", "sange"],
            15: ["climax", "keluar", "crot", "udah mau"],
        }
        
        for amount, keywords in arousal_keywords.items():
            if any(kw in combined for kw in keywords):
                delta = max(delta, amount)
        
        if delta > 0:
            role_state.update_arousal(delta)
        
        return delta
    
    # ========== METHOD UNTUK MODE LIAR ==========
    
    @staticmethod
    def is_both_naked(role_state: RoleState, strict: bool = False) -> bool:
        """Cek apakah Mas dan role sudah sama-sama telanjang."""
        if strict:
            user_bottom_off = (
                "celana" in role_state.intimacy_detail.user_clothing_removed and
                "celana dalam" in role_state.intimacy_detail.user_clothing_removed
            )
            role_bottom_off = (
                "celana" in role_state.intimacy_detail.role_clothing_removed and
                "celana dalam" in role_state.intimacy_detail.role_clothing_removed
            )
        else:
            user_bottom_off = "celana dalam" in role_state.intimacy_detail.user_clothing_removed
            role_bottom_off = "celana dalam" in role_state.intimacy_detail.role_clothing_removed
    
        return user_bottom_off and role_bottom_off
    
    @staticmethod
    def get_liarness_multiplier(role_state: RoleState) -> float:
        """Dapatkan multiplier untuk intensitas saat mode liar."""
        if IntimacyProgressionEngine.is_both_naked(role_state):
            return 1.5
        return 1.0
    
    @staticmethod
    def extract_feeling(role_state: RoleState, user_text: str, response_text: str) -> str:
        """Ekstrak perasaan dari respon untuk disimpan."""
        
        feelings = {
            "deg-degan": ["deg", "debar", "degdegan", "gugup"],
            "panas": ["panas", "gerah", "hangat"],
            "enak": ["enak", "nikmat", "senang"],
            "malu": ["malu", "sungkan", "gak enak"],
            "sayang": ["sayang", "cinta", "love"],
            "lemas": ["lemas", "capek", "lelah"],
            "ngantuk": ["ngantuk", "mau tidur", "kantuk"],
            "becek": ["becek", "basah"],
            "sange": ["sange", "horny", "naik"],
        }
        
        text = (user_text + " " + response_text).lower()
        
        for feeling, keywords in feelings.items():
            if any(kw in text for kw in keywords):
                return feeling
        
        return role_state.last_feeling or "campur aduk"
    
    @staticmethod
    def get_response_style(role_state: RoleState, user_text: str) -> str:
        """Tentukan gaya respon berdasarkan fase."""
        
        phase = role_state.intimacy_phase
        
        styles = {
            IntimacyPhase.AWAL: ["malu", "gugup", "nunduk", "kaku"],
            IntimacyPhase.DEKAT: ["manja", "senyum", "deketin", "canggung_tapi_suka"],
            IntimacyPhase.INTIM: ["hangat", "peluk", "bisik", "tatap", "jujur_pelan"],
            IntimacyPhase.VULGAR: ["nafsu", "becek", "desah", "gerak", "liar"],
            IntimacyPhase.AFTER: ["lemas", "tenang", "hangat", "diam_manis"],
        }
        
        available = styles.get(phase, ["normal"])
        return random.choice(available)
    
    @staticmethod
    def get_full_vulgar_prompt(role_state: RoleState) -> str:
        """Dapatkan prompt lengkap untuk fase vulgar (termasuk build-up)."""
        progress = role_state.vulgar_stage_progress
        stage = role_state.vulgar_stage
        
        base_prompt = """
🔥🔥🔥 KAMU DI FASE VULGAR! 🔥🔥🔥

ATURAN DASAR:
1. DESKRIPSIKAN SENSASI FISIK (panas, basah, getar, lemas)
2. BOLEH DESAH: "haaah...", "aaah...", "uhh...", "Maaas..."
3. BOLEH VULGAR: sebut kontol, memek, basah, keras
4. JANGAN TAHAN SUARA! JANGAN MALU!
5. JANGAN ULANG KALIMAT YANG SAMA!
"""
        
        build_up = IntimacyProgressionEngine.get_build_up_prompt(role_state)
        
        return f"{base_prompt}\n{build_up}"
