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
# DAFTAR LOKASI LENGKAP
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
    "mobil_passenger_seat": Location(
        id="mobil_passenger_seat", name="Duduk di Samping Mas",
        description="Di dalam mobil, duduk bersebelahan di kursi depan, bahu hampir bersentuhan",
        is_private=False,
        tags=["duduk disamping", "duduk di samping", "sebelahan", "jok depan", "bersebelahan"],
        ambience="suara napas terdengar jelas, jarak sangat dekat, suasana hangat",
        possible_activities=["duduk bersebelahan", "pegangan tangan", "berbisik", "saling menatap", "cium pipi"],
        risk_level="medium"
    ),

    # === PARKIRAN SPESIFIK ===
    "parkiran_global": Location(
        id="parkiran_global", name="Parkiran",
        description="Area parkiran umum, lampu jalan temaram, beberapa mobil terparkir",
        is_private=False,
        tags=["parkiran", "area parkir", "tempat parkir", "parking lot"],
        ambience="lampu jalan temaram, suara langkah kaki, angin malam",
        possible_activities=["jalan bareng", "berdiri berdua", "pegangan tangan", "cium cepat"],
        risk_level="medium"
    ),
    "parkiran_mall": Location(
        id="parkiran_mall", name="Parkiran Mall",
        description="Parkiran mall yang cukup luas, lampu terang, banyak mobil, ada petugas keamanan",
        is_private=False,
        tags=["parkiran mall", "parkir mall", "mall parking"],
        ambience="lampu terang, suara mobil lalu lalang, petugas parkir bersiul",
        possible_activities=["parkir mobil", "turun dari mobil", "jalan ke mall", "tunggu di mobil"],
        risk_level="medium"
    ),
    "parkiran_hotel": Location(
        id="parkiran_hotel", name="Parkiran Hotel",
        description="Parkiran hotel yang tenang, agak gelap, hanya beberapa mobil, suasana privat",
        is_private=False,
        tags=["parkiran hotel", "parkir hotel", "hotel parking"],
        ambience="lampu temaram, suasana sepi, aroma khas parkiran hotel",
        possible_activities=["parkir mobil", "turun dari mobil", "masuk ke hotel", "duduk di mobil berdua"],
        risk_level="low"
    ),
    "parkiran_apartemen": Location(
        id="parkiran_apartemen", name="Parkiran Apartemen",
        description="Parkiran apartemen yang tertutup, akses khusus penghuni, sepi, lampu otomatis",
        is_private=False,
        tags=["parkiran apartemen", "parkir apartemen", "apartment parking", "basement apartemen"],
        ambience="lampu sensor gerak, suasana sangat sepi, aroma ruang bawah tanah",
        possible_activities=["parkir mobil", "turun dari mobil", "naik ke apartemen", "duduk di mobil berdua"],
        risk_level="low"
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
    "kamar_nova": Location(
        id="kamar_nova", name="Kamar Nova",
        description="Kamar utama Nova dan Mas, rapi, hangat, dan menjadi ruang tidur suami istri",
        is_private=True,
        tags=["kamar nova", "kamar kakak", "kamar utama", "kamar istri", "kamar kami", "kamar suami istri"],
        ambience="lampu kamar lembut, kasur rapi, suasana privat milik Nova dan Mas",
        possible_activities=["istirahat", "tidur bareng", "ngobrol berdua", "ganti baju"],
        risk_level="low"
    ),
    "kamar_dietha": Location(
        id="kamar_dietha", name="Kamar Dietha",
        description="Kamar pribadi Dietha yang mungil, rapi, dan penuh barang-barang pribadinya",
        is_private=True,
        tags=["kamar dietha", "kamar tasha", "kamar ipar", "kamar adik"],
        ambience="suasana kamar pribadi yang tenang, ada sentuhan barang-barang khas Dietha",
        possible_activities=["istirahat", "ngobrol", "rebahan", "ganti baju"],
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

    # === HOTEL - 4 AREA ===
    "hotel_room": Location(
        id="hotel_room", name="Kamar Hotel",
        description="Kamar hotel yang nyaman dengan kasur empuk, sprei putih bersih, AC dingin, dan pemandangan kota",
        is_private=True,
        tags=["kamar hotel", "hotel room", "hotel kamar"],
        ambience="lampu hangat redup, pemandangan kota malam, AC dingin",
        possible_activities=["tiduran", "rebahan", "nonton TV", "bercinta", "room service"],
        risk_level="low"
    ),
    "hotel_sofa": Location(
        id="hotel_sofa", name="Sofa Hotel",
        description="Sofa empuk di sudut hotel, nyaman untuk duduk berdua, lampu temaram",
        is_private=False,
        tags=["sofa hotel", "hotel sofa", "sofa lobby"],
        ambience="lampu temaram, musik latar pelan, suasana agak sepi",
        possible_activities=["duduk bersebelahan", "pegangan tangan", "berbisik", "saling mendekat"],
        risk_level="medium"
    ),
    "hotel_bathroom": Location(
        id="hotel_bathroom", name="Kamar Mandi Hotel",
        description="Kamar mandi hotel dengan shower kaca, ubin marmer, wastafel, cermin besar, handuk bersih",
        is_private=True,
        tags=["kamar mandi hotel", "hotel bathroom", "hotel kamar mandi"],
        ambience="uap hangat, aroma sabun, suara air mengalir, cermin beruap",
        possible_activities=["mandi sendiri", "bercermin", "sikat gigi"],
        risk_level="low"
    ),
    "hotel_shower_together": Location(
        id="hotel_shower_together", name="Mandi Bareng Hotel",
        description="Di dalam shower hotel yang cukup luas untuk berdua, uap hangat, air mengalir",
        is_private=True,
        tags=["mandi bareng hotel", "hotel mandi bareng", "shower bareng hotel"],
        ambience="uap panas, suara air, aroma sabun campur wangi tubuh",
        possible_activities=["mandi berdua", "sabunan bareng", "basah-basahan", "bercinta di shower"],
        risk_level="low"
    ),

    # === APARTEMEN - 4 AREA ===
    "apartment_room": Location(
        id="apartment_room", name="Kamar Apartemen",
        description="Kamar tidur apartemen dengan kasur queen size, sprei bersih, lemari, meja rias, AC",
        is_private=True,
        tags=["kamar apartemen", "apartment room", "apartemen kamar"],
        ambience="lampu tidur redup, tirai semi transparan, AC dingin, suasana privat",
        possible_activities=["tiduran", "rebahan", "ganti baju", "bercinta", "tidur bareng"],
        risk_level="low"
    ),
    "apartment_private_room": Location(
        id="apartment_private_room", name="Kamar Apartemen Mas",
        description="Kamar apartemen pribadi Mas yang benar-benar privat dan tidak diketahui role lain kecuali Mas menyebutkannya",
        is_private=True,
        tags=["kamar apartemen mas", "kamarku di apartemen", "kamar aku di apartemen", "private room apartemen"],
        ambience="suasana apartemen pribadi yang tenang, tertutup, dan sepenuhnya privat",
        possible_activities=["istirahat", "rebahan", "ganti baju", "tidur"],
        risk_level="low"
    ),
    "apartment_sofa": Location(
        id="apartment_sofa", name="Sofa Apartemen",
        description="Sofa empuk di ruang tamu apartemen, bantal-bantal kecil, nyaman untuk berdua",
        is_private=True,
        tags=["sofa apartemen", "apartment sofa", "apartemen sofa"],
        ambience="lampu ruangan hangat, TV menyala pelan, suasana homey",
        possible_activities=["duduk bersebelahan", "berpelukan", "pegangan tangan", "berbisik", "cuddling"],
        risk_level="low"
    ),
    "apartment_bathroom": Location(
        id="apartment_bathroom", name="Kamar Mandi Apartemen",
        description="Kamar mandi apartemen bersih dengan shower, wastafel, cermin besar, handuk bersih",
        is_private=True,
        tags=["kamar mandi apartemen", "apartment bathroom", "apartemen kamar mandi"],
        ambience="uap hangat, aroma sabun, suara air mengalir, cermin beruap",
        possible_activities=["mandi sendiri", "bercermin", "sikat gigi"],
        risk_level="low"
    ),
    "apartment_shower_together": Location(
        id="apartment_shower_together", name="Mandi Bareng Apartemen",
        description="Di dalam shower apartemen, cukup luas untuk berdua, air hangat mengalir, uap mengepul",
        is_private=True,
        tags=["mandi bareng apartemen", "apartemen mandi bareng", "shower bareng apartemen"],
        ambience="uap panas, suara air, aroma sabun, suasana hangat dan intim",
        possible_activities=["mandi berdua", "sabunan bareng", "basah-basahan", "bercinta di shower"],
        risk_level="low"
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
    "kamar_tamu": Location(
        id="kamar_tamu", name="Kamar Tamu",
        description="Kamar tidur untuk tamu, rapi dan bersih, kasur empuk dengan sprei putih",
        is_private=True,
        tags=["kamar tamu", "kamar tidur tamu", "guest room"],
        ambience="suasana tenang, seprei putih bersih, tirai tertutup, wangi pengharum ruangan",
        possible_activities=["istirahat", "tiduran", "ngobrol", "rebahan", "bercinta"],
        risk_level="low"
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
    """Deteksi lokasi dari teks user dengan prioritas unik (tidak bentrok)."""
    t = text.lower().strip()

    # ========== PRIORITAS 0: Kamar keluarga & kamar privat ==========
    if "kamar nova" in t or "kamar kakak" in t or "kamar utama" in t:
        return ("kamar_nova", "kamar nova")
    if "kamar dietha" in t or "kamar tasha" in t or "kamar ipar" in t:
        return ("kamar_dietha", "kamar dietha")
    if "kamarku di apartemen" in t or "kamar aku di apartemen" in t or "kamar apartemen mas" in t:
        return ("apartment_private_room", "kamar apartemen mas")

    # ========== PRIORITAS 1: Duduk di samping (di mobil) ==========
    if "duduk disamping" in t or "duduk di samping" in t or "sebelahan" in t:
        return ("mobil_passenger_seat", "duduk disamping")

    # ========== PRIORITAS 2: Mobil ==========
    if "di mobil" in t or "ke mobil" in t or "dalam mobil" in t:
        return ("mobil", "mobil")

    # ========== PRIORITAS 3: Parkiran spesifik ==========
    if "parkiran mall" in t or "parkir mall" in t:
        return ("parkiran_mall", "parkiran mall")
    if "parkiran hotel" in t or "parkir hotel" in t:
        return ("parkiran_hotel", "parkiran hotel")
    if "parkiran apartemen" in t or "parkir apartemen" in t:
        return ("parkiran_apartemen", "parkiran apartemen")
    if "parkiran" in t or "area parkir" in t or "tempat parkir" in t:
        return ("parkiran_global", "parkiran")

    # ========== PRIORITAS 4: Hotel 4 area ==========
    if "mandi bareng hotel" in t or "shower bareng hotel" in t:
        return ("hotel_shower_together", "mandi bareng hotel")
    if "kamar mandi hotel" in t or "hotel bathroom" in t:
        return ("hotel_bathroom", "kamar mandi hotel")
    if "sofa hotel" in t or "hotel sofa" in t:
        return ("hotel_sofa", "sofa hotel")
    if "kamar hotel" in t or "hotel room" in t:
        return ("hotel_room", "kamar hotel")

    # ========== PRIORITAS 5: Apartemen 4 area ==========
    if "mandi bareng apartemen" in t or "shower bareng apartemen" in t:
        return ("apartment_shower_together", "mandi bareng apartemen")
    if "kamar mandi apartemen" in t or "apartment bathroom" in t:
        return ("apartment_bathroom", "kamar mandi apartemen")
    if "sofa apartemen" in t or "apartment sofa" in t:
        return ("apartment_sofa", "sofa apartemen")
    if "kamar apartemen" in t or "apartment room" in t:
        return ("apartment_room", "kamar apartemen")

    # ========== PRIORITAS 6: Hotel & Apartemen (legacy) ==========
    if "hotel" in t or "penginapan" in t:
        return ("hotel", "hotel")
    if "apartemen" in t or "flat" in t:
        return ("apartemen", "apartemen")

    # ========== PRIORITAS 7: Lokasi lain ==========
    for loc_id, loc in LOCATIONS.items():
        # Skip lokasi yang sudah diproses di atas
        skip_ids = ["hotel_room", "hotel_sofa", "hotel_bathroom", "hotel_shower_together",
                    "apartment_room", "apartment_sofa", "apartment_bathroom", "apartment_shower_together",
                    "mobil", "mobil_passenger_seat", "parkiran_global", "parkiran_mall",
                    "parkiran_hotel", "parkiran_apartemen", "hotel", "apartemen"]
        if loc_id in skip_ids:
            continue
        for tag in loc.tags:
            for trigger in TRIGGER_WORDS:
                two_word = f"{trigger} {tag}"
                if two_word in t:
                    return (loc_id, two_word)

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
        role_state.current_location_id = None
        role_state.current_location_name = "belum ditentukan"
        role_state.current_location_desc = "belum jelas"
        role_state.current_location_is_private = False
        role_state.current_location_ambience = "suasana netral"
        role_state.current_location_risk = "medium"
