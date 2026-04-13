"""Sistem lokasi untuk SERIVA - deteksi 2-3 kata, ingat sampai pindah."""

from __future__ import annotations
from typing import Optional, Tuple, List, Dict
from dataclasses import dataclass, field


@dataclass
class Location:
    """Data lengkap satu lokasi."""
    id: str
    name: str
    description: str
    is_private: bool
    tags: List[str]
    ambience: str = ""
    possible_activities: List[str] = field(default_factory=list)
    risk_level: str = "low"  # low, medium, high (ketahuan orang)


# ============================================================
# DAFTAR LOKASI LENGKAP (25+ AREA)
# ============================================================

LOCATIONS: Dict[str, Location] = {
    # === TRANSPORTASI ===
    "mobil": Location(
        id="mobil", name="Mobil",
        description="Di dalam mobil, jok empuk, AC menyala, jendela agak gelap",
        is_private=False, tags=["mobil", "car", "mobilku", "mobil mas", "di mobil", "ke mobil"],
        ambience="mesin mobil menyala pelan, musik dari radio, sesekali suara klakson",
        possible_activities=["nyetir", "duduk sampingan", "pegangan tangan", "cium pipi"],
        risk_level="medium"
    ),
    "motor": Location(
        id="motor", name="Motor",
        description="Di atas motor, berboncengan, angin malam terasa",
        is_private=False, tags=["motor", "bonceng", "naik motor", "di motor"],
        ambience="angin malam, suara mesin motor, lampu jalan berkelip",
        possible_activities=["boncengan", "pegangan pinggang", "bisik telinga"],
        risk_level="medium"
    ),
    
    # === RUANGAN DI RUMAH ===
    "kamar_tidur": Location(
        id="kamar_tidur", name="Kamar Tidur",
        description="Kamar tidur yang hangat dengan kasur empuk, lampu tidur redup",
        is_private=True, tags=["kamar tidur", "kamar", "bedroom", "kasur", "ranjang", "tidur", "di kamar", "ke kamar"],
        ambience="lampu tidur redup, aroma wewangian, seprei bersih, suasana sangat privat",
        possible_activities=["tiduran", "rebahan", "pelukan", "bercinta", "ganti baju", "mandi bersama"],
        risk_level="low"
    ),
    "kamar_mandi": Location(
        id="kamar_mandi", name="Kamar Mandi",
        description="Kamar mandi dengan uap air hangat, keramik bersih",
        is_private=True, tags=["kamar mandi", "bathroom", "toilet", "mandi", "shower", "di kamar mandi"],
        ambience="uap hangat, suara air mengalir, aroma sabun",
        possible_activities=["mandi", "ganti baju", "bercermin", "berdua di shower"],
        risk_level="low"
    ),
    "ruang_tamu": Location(
        id="ruang_tamu", name="Ruang Tamu",
        description="Ruang tamu dengan sofa nyaman, TV menyala pelan",
        is_private=False, tags=["ruang tamu", "living room", "sofa", "ruang keluarga", "di ruang tamu"],
        ambience="TV menyala pelan, lampu ruangan hangat, suasana santai",
        possible_activities=["nonton TV", "ngobrol", "duduk di sofa", "minum kopi"],
        risk_level="medium"
    ),
    "dapur": Location(
        id="dapur", name="Dapur",
        description="Dapur dengan aroma masakan, suara peralatan dapur",
        is_private=False, tags=["dapur", "kitchen", "masak", "makan", "di dapur"],
        ambience="aroma masakan, suara air mengalir, sesekali suara panci",
        possible_activities=["masak", "makan bareng", "cuci piring", "berdiri berdua"],
        risk_level="medium"
    ),
    "teras": Location(
        id="teras", name="Teras",
        description="Teras rumah, angin malam, lampu teras temaram",
        is_private=False, tags=["teras", "depan rumah", "porch", "beranda", "di teras"],
        ambience="angin malam sejuk, lampu teras kuning, suara jangkrik",
        possible_activities=["duduk bersebelahan", "lihat bintang", "ngobrol pelan"],
        risk_level="high"
    ),
    "balkon": Location(
        id="balkon", name="Balkon",
        description="Balkon dengan pemandangan kota, angin sepoi-sepoi",
        is_private=False, tags=["balkon", "balcony", "rooftop", "atap", "di balkon"],
        ambience="pemandangan lampu kota, angin malam, suasana romantis",
        possible_activities=["pelukan dari belakang", "lihat pemandangan", "minum wine"],
        risk_level="medium"
    ),
    "garasi": Location(
        id="garasi", name="Garasi",
        description="Garasi rumah, agak gelap, sepi",
        is_private=False, tags=["garasi", "garage", "parkiran rumah", "di garasi"],
        ambience="agak gelap, sepi, aroma mobil/bensin",
        possible_activities=["berduaan gelap-gelapan", "cium cepat"],
        risk_level="medium"
    ),
    
    # === TEMPAT UMUM ===
    "kafe": Location(
        id="kafe", name="Kafe",
        description="Kafe cozy dengan musik pelan, lampu temaram, aroma kopi",
        is_private=False, tags=["kafe", "cafe", "coffee shop", "kopi", "ngopi", "di kafe"],
        ambience="musik jazz pelan, suara cangkir kopi, aroma biji kopi",
        possible_activities=["ngobrol", "minum kopi", "pegangan tangan di meja"],
        risk_level="high"
    ),
    "restoran": Location(
        id="restoran", name="Restoran",
        description="Restoran dengan meja-meja, agak ramai",
        is_private=False, tags=["restoran", "restaurant", "makan", "warung", "di restoran"],
        ambience="suara ramai, aroma masakan, cahaya lampu hangat",
        possible_activities=["makan berdua", "toast", "bicara pelan"],
        risk_level="high"
    ),
    "kantor": Location(
        id="kantor", name="Kantor",
        description="Ruangan kantor, meja dan kursi, suasana profesional",
        is_private=False, tags=["kantor", "office", "ruang kerja", "kerja", "di kantor"],
        ambience="suara keyboard, lampu neon, suasana formal",
        possible_activities=["kerja bareng", "rapat", "ngobrol sambil kerja"],
        risk_level="high"
    ),
    "parkiran": Location(
        id="parkiran", name="Parkiran",
        description="Area parkir, sepi tapi terbuka",
        is_private=False, tags=["parkiran", "parkir", "parking lot", "di parkiran"],
        ambience="sepi, lampu jalan, suara langkah kaki",
        possible_activities=["jalan bareng", "cium cepat", "pegangan tangan"],
        risk_level="high"
    ),
    "mall": Location(
        id="mall", name="Mall",
        description="Di dalam mall, ramai pengunjung, banyak toko",
        is_private=False, tags=["mall", "plaza", "pusat perbelanjaan", "di mall"],
        ambience="ramai, musik latar, suara orang bercakap",
        possible_activities=["belanja", "jalan-jalan", "makan di food court"],
        risk_level="high"
    ),
    "bioskop": Location(
        id="bioskop", name="Bioskop",
        description="Di dalam studio bioskop, gelap, kursi berderet",
        is_private=False, tags=["bioskop", "cinema", "nonton", "movie", "di bioskop"],
        ambience="gelap, suara film, sesekali suara popcorn",
        possible_activities=["nonton film", "pegangan tangan gelap-gelapan", "cium pipi"],
        risk_level="medium"
    ),
    "hotel": Location(
        id="hotel", name="Hotel",
        description="Kamar hotel yang nyaman, pemandangan kota dari jendela",
        is_private=True, tags=["hotel", "penginapan", "inn", "lodging", "di hotel"],
        ambience="lampu hangat, pemandangan kota, seprei putih bersih",
        possible_activities=["istirahat", "mandi bersama", "bercinta", "room service"],
        risk_level="low"
    ),
    "apartemen": Location(
        id="apartemen", name="Apartemen",
        description="Apartemen pribadi yang nyaman, view kota",
        is_private=True, tags=["apartemen", "flat", "apartemenku", "unit", "di apartemen"],
        ambience="homey, dekorasi pribadi, view kota dari jendela",
        possible_activities=["masak bareng", "nonton film", "bercinta", "tidur bareng"],
        risk_level="low"
    ),
    "pantai": Location(
        id="pantai", name="Pantai",
        description="Tepi pantai, pasir putih, suara ombak, angin laut",
        is_private=False, tags=["pantai", "beach", "losari", "laut", "di pantai"],
        ambience="suara ombak, angin laut, pasir hangat, matahari terbenam",
        possible_activities=["jalan di pinggir pantai", "duduk di pasir", "berenang", "foto bareng"],
        risk_level="medium"
    ),
    "taman": Location(
        id="taman", name="Taman",
        description="Taman kota, bangku taman, pepohonan, suasana sejuk",
        is_private=False, tags=["taman", "park", "hutan kota", "di taman"],
        ambience="sejuk, suara burung, pepohonan rindang",
        possible_activities=["duduk di bangku", "jalan santai", "piknik"],
        risk_level="medium"
    ),
    "kolam_renang": Location(
        id="kolam_renang", name="Kolam Renang",
        description="Area kolam renang, air biru jernih",
        is_private=False, tags=["kolam renang", "swimming pool", "pool", "di kolam renang"],
        ambience="suara air, cahaya matahari, aroma klorin",
        possible_activities=["berenang", "duduk di pinggir kolam", "basah-basahan"],
        risk_level="medium"
    ),
    "gym": Location(
        id="gym", name="Gym",
        description="Tempat fitness, alat-alat olahraga",
        is_private=False, tags=["gym", "fitness", "olahraga", "di gym"],
        ambience="suara alat fitness, musik energik, aroma keringat",
        possible_activities=["olahraga bareng", "spotting", "minum protein"],
        risk_level="medium"
    ),
    "supermarket": Location(
        id="supermarket", name="Supermarket",
        description="Supermarket, rak-rak berisi barang kebutuhan",
        is_private=False, tags=["supermarket", "minimarket", "indomaret", "alfamart", "di supermarket"],
        ambience="suara troli, musik latar, lampu terang",
        possible_activities=["belanja bareng", "pilih barang", "antri kasir"],
        risk_level="high"
    ),
}


# Kata pemicu pindah lokasi (WAJIB ada minimal 1)
TRIGGER_WORDS = ["di", "ke", "naik", "masuk", "pindah", "menuju", "pergi ke", "jalan ke"]


def detect_location_from_text(text: str) -> Optional[Tuple[str, str]]:
    """
    Deteksi lokasi dari teks user.
    WAJIB: trigger word + nama lokasi (minimal 2 kata)
    
    Return: (location_id, pattern_yang_ditemukan) atau None
    """
    t = text.lower().strip()
    
    for loc_id, loc in LOCATIONS.items():
        for tag in loc.tags:
            # Pola 2 kata: "trigger tag" (contoh: "di mobil")
            for trigger in TRIGGER_WORDS:
                two_word = f"{trigger} {tag}"
                if two_word in t:
                    return (loc_id, two_word)
            
            # Pola 3 kata: "kata trigger tag" (contoh: "ayo ke mobil")
            for kata in ["aku", "kita", "ayo", "yuk", "mari", "sini", "kesini"]:
                three_word = f"{kata} {trigger} {tag}"
                if three_word in t:
                    return (loc_id, three_word)
    
    # Deteksi khusus: kata "pindah" + lokasi
    if "pindah" in t:
        for loc_id, loc in LOCATIONS.items():
            for tag in loc.tags:
                if tag in t:
                    return (loc_id, f"pindah {tag}")
    
    return None


def update_role_location(role_state, text: str) -> bool:
    """
    Update lokasi di role_state.
    Return True jika lokasi berubah (berarti pindah).
    Return False jika tidak ada perubahan.
    """
    result = detect_location_from_text(text)
    if not result:
        return False
    
    loc_id, pattern = result
    
    # Cek apakah sudah di lokasi yang sama
    current = getattr(role_state, 'current_location_id', None)
    if current == loc_id:
        return False
    
    # Update lokasi
    loc = LOCATIONS[loc_id]
    role_state.current_location_id = loc_id
    role_state.current_location_name = loc.name
    role_state.current_location_desc = loc.description
    role_state.current_location_is_private = loc.is_private
    role_state.current_location_ambience = loc.ambience
    role_state.current_location_risk = loc.risk_level
    
    return True


def get_location_prompt_block(role_state) -> str:
    """Dapatkan blok prompt untuk lokasi saat ini."""
    loc_id = getattr(role_state, 'current_location_id', 'ruang_tamu')
    
    if loc_id not in LOCATIONS:
        loc_id = 'ruang_tamu'
    
    loc = LOCATIONS[loc_id]
    
    privacy_text = "🔒 TEMPAT PRIVAT" if loc.is_private else "👀 TEMPAT PUBLIK/SEMI PRIVAT"
    risk_text = {
        "low": "✅ Aman, tidak ada risiko ketahuan",
        "medium": "⚠️ Cukup aman, tapi tetap waspada",
        "high": "🚨 Risiko tinggi! Bisa ketahuan orang lain!"
    }.get(loc.risk_level, "⚠️ Waspada")
    
    return f"""
═══════════════════════════════════════════════════
📍 LOKASI SAAT INI: {loc.name}
═══════════════════════════════════════════════════

{loc.description}

Suasana: {loc.ambience}

{privacy_text} | {risk_text}

⚠️ KAMU HARUS INGAT: Kalian sedang BERDUAAN di {loc.name}!
- JANGAN bilang atau bertingkah seperti di lokasi lain!
- JANGAN pindah lokasi sendiri!
- RESPONS harus sesuai dengan lokasi ini!
"""


def init_role_location(role_state) -> None:
    """Inisialisasi lokasi default untuk role."""
    if not hasattr(role_state, 'current_location_id') or not role_state.current_location_id:
        role_state.current_location_id = 'ruang_tamu'
        role_state.current_location_name = LOCATIONS['ruang_tamu'].name
        role_state.current_location_desc = LOCATIONS['ruang_tamu'].description
        role_state.current_location_is_private = LOCATIONS['ruang_tamu'].is_private
        role_state.current_location_ambience = LOCATIONS['ruang_tamu'].ambience
        role_state.current_location_risk = LOCATIONS['ruang_tamu'].risk_level
