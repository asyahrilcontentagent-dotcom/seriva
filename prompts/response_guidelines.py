"""Panduan respon untuk SERIVA - VERSI SIMPEL (SEMUA ATURAN DINONAKTIFKAN)

File ini disederhanakan agar role bisa merespon secara NATURAL
tanpa dipaksa mengikuti aturan progres, stage, atau template.
"""

from __future__ import annotations

from core.state_models import IntimacyPhase, SceneSequence


# ============================================================
# PANDUAN RESPON SIMPEL (TANPA ATURAN KAKU)
# ============================================================

SIMPLE_GUIDELINES = """
═══════════════════════════════════════════════════════════════════
📌 PANDUAN RESPON SIMPEL
═══════════════════════════════════════════════════════════════════

Cukup ikuti 3 aturan ini:

1. RESPON NATURAL, seperti orang chat sungguhan
2. INGAT obrolan sebelumnya (jangan mulai dari nol terus)
3. LANJUTKAN dari momen terakhir

Tidak perlu:
- Menghitung progres
- Memaksakan climax
- Mengikuti template gesture
- Memikirkan stage vulgar

Yang penting:
- Natural
- Konsisten dengan karakter
- Lanjut dari obrolan sebelumnya

═══════════════════════════════════════════════════════════════════
"""


def get_response_guidelines(phase: IntimacyPhase = IntimacyPhase.AWAL, 
                            intimacy_intensity: int = 1,
                            current_sequence: SceneSequence = None,
                            vulgar_stage: str = "awal",
                            vulgar_progress: int = 0) -> str:
    """Dapatkan panduan respon simpel untuk dimasukkan ke system prompt.
    
    SEMUA ATURAN DINONAKTIFKAN.
    """
    
    return SIMPLE_GUIDELINES


def get_response_guidelines_legacy() -> str:
    """Versi lama untuk kompatibilitas - sekarang return versi simpel."""
    return SIMPLE_GUIDELINES
