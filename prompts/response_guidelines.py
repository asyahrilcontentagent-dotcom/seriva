"""Panduan respon untuk SERIVA - VERSI KOSONG (SEMUA ATURAN DINONAKTIFKAN)

File ini dikosongkan agar role bisa merespon secara NATURAL
tanpa dipengaruhi aturan apapun dari file ini.
"""

from __future__ import annotations

from core.state_models import IntimacyPhase, SceneSequence


def get_response_guidelines(phase: IntimacyPhase = IntimacyPhase.AWAL, 
                            intimacy_intensity: int = 1,
                            current_sequence: SceneSequence = None,
                            vulgar_stage: str = "awal",
                            vulgar_progress: int = 0) -> str:
    """Panduan respon - DINONAKTIFKAN TOTAL"""
    return ""


def get_response_guidelines_legacy() -> str:
    """Versi lama untuk kompatibilitas - DINONAKTIFKAN"""
    return ""
