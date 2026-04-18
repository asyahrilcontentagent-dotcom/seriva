"""Intimacy Progression Engine untuk SERIVA - DINONAKTIFKAN TOTAL

Semua method yang mengontrol fase, progres vulgar, climax, dll. dinonaktifkan
agar role bisa merespon secara NATURAL tanpa aturan kaku.
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
    """Engine untuk menentukan fase intimacy berdasarkan interaksi - DINONAKTIFKAN"""
    
    # Threshold untuk pindah fase (TIDAK DIPAKAI)
    THRESHOLDS = {
        IntimacyPhase.DEKAT: {
            "min_turns": 2,
            "keywords": ["dekat", "mepet", "bersentuhan", "nyender", "pegang tangan"],
        },
        IntimacyPhase.INTIM: {
            "min_turns": 3,
            "keywords": ["peluk", "rangkul", "genggam", "napas", "dada", "pelukan"],
        },
        IntimacyPhase.VULGAR: {
            "min_turns": 8,
            "keywords": ["kontol", "memek", "becek", "keras", "masuk", "ngewe", "sex"],
        },
    }

    @staticmethod
    def _has_strong_climax_trigger(text: str) -> bool:
        """DINONAKTIFKAN"""
        return False

    @staticmethod
    def _has_sensitive_touch_from_user(text: str) -> bool:
        """DINONAKTIFKAN"""
        return False

    @staticmethod
    def _has_user_body_touch(text: str) -> bool:
        """DINONAKTIFKAN"""
        return False

    @staticmethod
    def _get_risk_deescalation_target(text: str) -> Optional[IntimacyPhase]:
        """DINONAKTIFKAN"""
        return None
    
    @classmethod
    def update_phase_and_scene(cls, role_state: RoleState, user_text: str, response_text: str) -> bool:
        """DINONAKTIFKAN - role bebas menentukan fasenya sendiri"""
        return False

    # ========== VULGAR INVITATION METHODS (DINONAKTIFKAN) ==========
    
    @classmethod
    def has_user_invited_to_vulgar(cls, role_state: RoleState, user_text: str) -> bool:
        """DINONAKTIFKAN - langsung True"""
        return True
    
    @classmethod
    def has_role_invited_to_vulgar(cls, role_state: RoleState, response_text: str) -> bool:
        """DINONAKTIFKAN - langsung True"""
        return True
    
    @classmethod
    def can_enter_vulgar_phase(cls, role_state: RoleState, user_text: str = "", response_text: str = "") -> tuple[bool, str]:
        """DINONAKTIFKAN - langsung True"""
        return True, "Bisa"
    
    @classmethod
    def extract_feeling(cls, role_state: RoleState, user_text: str, response_text: str) -> str:
        """Ekstrak perasaan dari respon untuk disimpan - tetap aktif"""
        
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
        """Tentukan gaya respon berdasarkan fase - versi simpel"""
        
        phase = role_state.intimacy_phase
        
        styles = {
            IntimacyPhase.AWAL: ["malu", "gugup", "nunduk", "kaku"],
            IntimacyPhase.DEKAT: ["manja", "senyum", "deketin", "canggung_tapi_suka", "penasaran_pelan"],
            IntimacyPhase.INTIM: ["hangat", "peluk", "bisik", "tatap", "jujur_pelan"],
            IntimacyPhase.VULGAR: ["nafsu", "becek", "desah", "gerak"],
            IntimacyPhase.AFTER: ["lemas", "tenang", "hangat", "diam_manis"],
        }
        
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
        """Reset semua state intimasi ke default untuk sesi baru."""
        role_state.reset_intimacy_state()
    
    # ========== LEVEL 10-12 PROGRESSION METHODS - DINONAKTIFKAN ==========
    
    @classmethod
    def update_vulgar_progression(cls, role_state: RoleState, user_text: str, response_text: str) -> Dict[str, any]:
        """DINONAKTIFKAN"""
        return {}
    
    @classmethod
    def _update_physical_state(cls, role_state: RoleState, text: str) -> None:
        """DINONAKTIFKAN"""
        pass
    
    @classmethod
    def get_vulgar_response_style(cls, role_state: RoleState) -> str:
        """DINONAKTIFKAN"""
        return ""
    
    @classmethod
    def check_and_execute_climax(cls, role_state: RoleState, user_text: str) -> Tuple[bool, str]:
        """DINONAKTIFKAN"""
        return (False, "")

    @classmethod
    def start_climax_countdown(cls, role_state: RoleState, user_text: str) -> Tuple[bool, str]:
        """DINONAKTIFKAN"""
        return (False, "")
    
    @classmethod
    def update_climax_countdown(cls, role_state: RoleState, user_text: str) -> Tuple[bool, str]:
        """DINONAKTIFKAN"""
        return (False, "")
    
    @classmethod
    def _execute_climax(cls, role_state: RoleState, reason: str) -> Tuple[bool, str]:
        """DINONAKTIFKAN"""
        return (False, "")
    
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

    # ========== VCS PROGRESSION METHODS - DINONAKTIFKAN ==========
    
    @classmethod
    def update_vcs_progression(cls, role_state: RoleState, user_text: str, response_text: str) -> Dict[str, any]:
        """DINONAKTIFKAN"""
        return {}
    
    @classmethod
    def check_and_execute_vcs_climax(cls, role_state: RoleState, user_text: str) -> Tuple[bool, str]:
        """DINONAKTIFKAN"""
        return (False, "")
    
    @classmethod
    def _execute_vcs_climax(cls, role_state: RoleState, reason: str) -> Tuple[bool, str]:
        """DINONAKTIFKAN"""
        return (False, "")

    # ========== METHOD UNTUK MODE LIAR - DINONAKTIFKAN ==========

    @classmethod
    def is_both_naked(cls, role_state: RoleState, strict: bool = False) -> bool:
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

    @classmethod
    def get_liarness_multiplier(cls, role_state: RoleState) -> float:
        """DINONAKTIFKAN"""
        return 1.0

    @classmethod
    def get_liar_response_style(cls, role_state: RoleState) -> str:
        """DINONAKTIFKAN"""
        return ""

    @classmethod
    def get_full_vulgar_prompt(cls, role_state: RoleState) -> str:
        """DINONAKTIFKAN"""
        return ""
