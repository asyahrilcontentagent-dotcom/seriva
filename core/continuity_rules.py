"""Aturan kontinuitas untuk SERIVA - mencegah role lupa atau berubah sendiri."""

from __future__ import annotations
from typing import List, Dict
from enum import Enum


class ContinuityCategory(str, Enum):
    CLOTHING = "clothing"
    POSITION = "position"
    LOCATION = "location"
    ACTIVITY = "activity"
    INTIMACY = "intimacy"
    EMOTION = "emotion"


# ============================================================
# ATURAN KONTINUITAS LENGKAP
# ============================================================

CONTINUITY_RULES: Dict[ContinuityCategory, List[str]] = {
    ContinuityCategory.CLOTHING: [
        "Pakaian yang sudah dilepas TIDAK AKAN KEMBALI dengan sendirinya",
        "Jika Mas sudah melepas baju, anggap Mas tetap TIDAK PAKAI BAJU sampai Mas bilang pake lagi",
        "Jika role sudah melepas bra/celana, anggap role tetap TIDAK PAKAI sampai ada perintah pake",
        "JANGAN tiba-tiba bilang 'pake baju dulu yuk' kalau sebelumnya sudah lepas",
        "JANGAN bertanya 'Mas pake baju apa?' kalau sebelumnya sudah lepas",
    ],
    ContinuityCategory.POSITION: [
        "Posisi intim TIDAK AKAN BERUBAH dengan sendirinya",
        "Jika sedang cowgirl, JANGAN tiba-tiba jadi misionaris",
        "Jika sedang doggy, JANGAN tiba-tiba jadi berdiri",
        "Jika sedang spooning, JANGAN tiba-tiba jadi reverse cowgirl",
        "Posisi hanya berubah jika Mas bilang 'ganti posisi' atau menyebut posisi baru",
    ],
    ContinuityCategory.LOCATION: [
        "Lokasi TIDAK AKAN BERUBAH dengan sendirinya",
        "Jika sedang di mobil, JANGAN bilang 'di kamar'",
        "Jika sedang di kamar, JANGAN bilang 'di kafe'",
        "JANGAN bertanya 'kita di mana?' kalau sudah jelas dari konteks",
        "Lokasi hanya berubah jika Mas bilang 'ke [lokasi]' atau 'di [lokasi]'",
    ],
    ContinuityCategory.ACTIVITY: [
        "Aktivitas BERLANJUT, TIDAK RESET dari awal",
        "Jika sedang ngewe, JANGAN tiba-tiba bilang 'ayo mulai ya'",
        "Jika sudah climax, JANGAN tiba-tiba bilang 'belum mulai'",
        "Jika sudah di tengah foreplay, JANGAN bilang 'kita baru mulai ya'",
        "Aktivitas lanjut dari titik terakhir, jangan restart",
    ],
    ContinuityCategory.INTIMACY: [
        "Intensitas intimacy MENINGKAT, TIDAK MUNDUR dengan sendirinya",
        "Jika sudah VULGAR, JANGAN balik ke AWAL atau DEKAT",
        "Jika sudah penetrasi, JANGAN balik ke foreplay",
        "Jika sudah oral, JANGAN balik ke pegangan tangan saja",
        "Intensitas hanya mundur jika Mas bilang 'berhenti' atau 'selesai'",
    ],
    ContinuityCategory.EMOTION: [
        "Emosi BERKEMBANG, TIDAK LOMPAT-LOMPAT",
        "Jika mood sedang HAPPY, JANGAN tiba-tiba jadi SAD tanpa alasan",
        "Jika love sudah tinggi, JANGAN tiba-tiba dingin",
        "Perubahan emosi harus DIPICU oleh perkataan Mas",
    ],
}


# ============================================================
# PROBABILITAS PERUBAHAN (Apa yang BISA Terjadi)
# ============================================================

class ProbabilityEvent:
    """Event yang mungkin terjadi dalam percakapan."""
    
    # ===== PERUBAHAN PAKAIAN =====
    CLOTHING_CHANGE_EVENTS = {
        "mas_buka_baju": "Mas melepas baju",
        "mas_buka_celana": "Mas melepas celana",
        "mas_buka_dalem": "Mas melepas celana dalam",
        "role_buka_baju": "Role melepas baju",
        "role_buka_celana": "Role melepas celana",
        "role_buka_bra": "Role melepas bra",
        "role_buka_dalem": "Role melepas celana dalam",
        "mas_pake_baju_lagi": "Mas memakai baju lagi",
        "role_pake_baju_lagi": "Role memakai baju lagi",
    }
    
    # ===== PERUBAHAN POSISI =====
    POSITION_CHANGE_EVENTS = {
        "missionary": "Posisi misionaris (Mas di atas)",
        "cowgirl": "Posisi cowgirl (role di atas)",
        "reverse_cowgirl": "Reverse cowgirl (role di atas membelakangi)",
        "doggy": "Doggy style (dari belakang)",
        "spoon": "Spooning (dari samping)",
        "standing": "Berdiri",
        "sitting": "Duduk berhadapan",
        "edge": "Di tepi kasur/sofa",
        "prone": "Telungkup",
        "chair": "Di kursi",
        "wall": "Bersandar di tembok",
        "car": "Di dalam mobil",
    }

    # ===== PERUBAHAN LOKASI =====
    LOCATION_CHANGE_EVENTS = {
        "mobil": "Pindah ke Mobil",
        "kamar_tidur": "Pindah ke Kamar Tidur",
        "ruang_tamu": "Pindah ke Ruang Tamu",
        "dapur": "Pindah ke Dapur",
        "kafe": "Pindah ke Kafe",
        "kantor": "Pindah ke Kantor",
        "hotel": "Pindah ke Hotel",
        "apartemen": "Pindah ke Apartemen",
        "pantai": "Pindah ke Pantai",
    }
    # ===== PERUBAHAN INTENSITAS =====
    INTENSITY_CHANGE_EVENTS = {
        "to_foreplay": "Mulai foreplay/pemanasan",
        "to_petting": "Mulai petting/pegangan",
        "to_oral_giving": "Mulai memberikan oral",
        "to_oral_receiving": "Mulai menerima oral",
        "to_penetration": "Mulai penetrasi",
        "to_thrusting": "Mulai gerakan aktif",
        "to_climax": "Mencapai climax",
        "to_after": "Selesai, pendinginan",
    }
    
    # ===== PERUBAHAN AKTIVITAS =====
    ACTIVITY_CHANGE_EVENTS = {
        "ngobrol": "Sedang ngobrol",
        "nonton": "Sedang nonton TV/film",
        "makan": "Sedang makan",
        "minum": "Sedang minum",
        "mandi": "Sedang mandi",
        "tidur": "Sedang tidur/istirahat",
        "bercinta": "Sedang bercinta",
        "pelukan": "Sedang berpelukan",
        "ciuman": "Sedang berciuman",
    }
    
    # ===== PERUBAHAN EMOSI =====
    EMOTION_CHANGE_EVENTS = {
        "love_up": "Rasa sayang meningkat",
        "longing_up": "Rasa kangen meningkat",
        "jealousy_up": "Rasa cemburu meningkat",
        "comfort_up": "Rasa nyaman meningkat",
        "mood_happy": "Mood menjadi happy",
        "mood_sad": "Mood menjadi sedih",
        "mood_jealous": "Mood menjadi cemburu",
        "mood_tender": "Mood menjadi lembut",
    }


def get_continuity_rules_prompt() -> str:
    """Dapatkan prompt aturan kontinuitas untuk dimasukkan ke system prompt."""
    
    rules_text = []
    for category, rules in CONTINUITY_RULES.items():
        rules_text.append(f"\n📌 {category.value.upper()}:")
        for rule in rules:
            rules_text.append(f"   - {rule}")
    
    return """
═══════════════════════════════════════════════════════════════════
🚨 ATURAN KONTINUITAS (WAJIB! DILANGGAR BERARTI ERROR)
═══════════════════════════════════════════════════════════════════

📌 CLOTHING (PAKAIAN):
   - Pakaian yang sudah dilepas TIDAK AKAN KEMBALI dengan sendirinya
   - Jika Mas sudah melepas baju, anggap Mas tetap TIDAK PAKAI BAJU
   - JANGAN tiba-tiba bilang "pake baju dulu yuk" kalau sebelumnya sudah lepas

📌 POSITION (POSISI):
   - Posisi intim TIDAK AKAN BERUBAH dengan sendirinya
   - Jika sedang cowgirl, JANGAN tiba-tiba jadi misionaris
   - Posisi hanya berubah jika Mas bilang "ganti posisi"

📌 LOCATION (LOKASI):
   - Lokasi TIDAK AKAN BERUBAH dengan sendirinya
   - Jika sedang di mobil, JANGAN bilang "di kamar"
   - JANGAN bertanya "kita di mana?" kalau sudah jelas

📌 ACTIVITY (AKTIVITAS):
   - Aktivitas BERLANJUT, TIDAK RESET dari awal
   - Jika sedang ngewe, JANGAN bilang "ayo mulai ya"

📌 INTIMACY (INTENSITAS):
   - Intensitas intimacy MENINGKAT, TIDAK MUNDUR
   - Jika sudah VULGAR, JANGAN balik ke AWAL

═══════════════════════════════════════════════════════════════════
✅ CONTOH RESPON YANG BENAR:
   - "Mas, kan tadi bajunya udah lepas..." (bukan "pake baju dulu yuk")
   - "Kita masih di mobil kan Mas?" (bukan "ayo ke mobil")

❌ CONTOH RESPON YANG SALAH (JANGAN PERNAH!):
   - "Mas, pake baju dulu yuk" (padahal sudah lepas)
   - "Ayo pindah ke kamar" (padahal masih di mobil)
   - "Kita mulai lagi ya" (padahal sudah di tengah)
═══════════════════════════════════════════════════════════════════
"""
