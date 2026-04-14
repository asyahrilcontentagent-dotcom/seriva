"""Auto-milestone rules for SERIVA.

Semua aturan untuk membuat milestone otomatis berdasarkan input user
per role dikumpulkan di sini, agar tidak memenuhi orchestrator.

Milestone yang di-handle saat ini:
- first_confession     : pertama kali bilang sayang/cinta
- first_hug            : pelukan pertama
- first_kiss_soft      : ciuman pertama (halus, non-vulgar)
- first_date_meal      : makan/date pertama
- first_movie_night    : nonton bareng pertama
- first_sleepover_soft : malam panjang pertama (tidur pelukan / ngobrol sampai ketiduran)
- soul_bonded_moment   : momen deep intimacy emosional (soul-bonded)

Semua milestone ini berlaku untuk role:
- Nova
- Ipar Tasha (Dietha)
- Teman kantor Ipeh
- Teman lama Widya
- Wanita bersuami Siska (Sika)
- Teman spesial Davina
- Teman spesial Sallsa

Terapis pijat TIDAK diberi milestone-milestone ini.
"""

from __future__ import annotations

from typing import Iterable

from config.constants import (
    ROLE_ID_NOVA,
    ROLE_ID_IPAR_TASHA,
    ROLE_ID_TEMAN_KANTOR_IPEH,
    ROLE_ID_TEMAN_LAMA_WIDYA,
    ROLE_ID_WANITA_BERSUAMI_SISKA,
    ROLE_ID_TEMAN_SPESIAL_DAVINA,
    ROLE_ID_TEMAN_SPESIAL_SALLSA,
)
from core.orchestrator import OrchestratorInput
from core.state_models import RoleState, UserState
from memory.milestones import MilestoneStore


# ==============================
# COMMON KEYWORDS
# ==============================

CONFESSION_KEYWORDS: list[str] = [
    "sayang",
    "cinta",
    "love you",
    "luv u",
    "aku suka kamu",
    "aku suka sama kamu",
]

HUG_KEYWORDS: list[str] = [
    "peluk",
    "pelukan",
    "memeluk",
    "kupeluk",
]

KISS_KEYWORDS: list[str] = [
    "cium",
    "ciuman",
    "kiss",
]

DATE_MEAL_KEYWORDS: list[str] = [
    "makan bareng",
    "makan berdua",
    "ngedate",
    "date",
    "ngopi bareng",
    "coffee date",
]

MOVIE_NIGHT_KEYWORDS: list[str] = [
    "nonton bareng",
    "nobar",
    "bioskop",
    "movie night",
    "nonton film",
]

SLEEPOVER_KEYWORDS: list[str] = [
    "tidur bareng",
    "malam panjang",
    "begadang bareng",
    "tidur dipelukan",
]

SOUL_BOND_KEYWORDS: list[str] = [
    "jiwa",
    "soul",
    "tak tergantikan",
    "nggak mau kehilangan",
    "gak mau kehilangan",
    "ga mau kehilangan",
    "rumahku",
    "tempat pulangku",
]


def _contains_any(text: str, keywords: list[str]) -> bool:
    t = text.lower()
    return any(kw in t for kw in keywords)


# ==============================
# ROLE SETS UNTUK MILESTONE
# ==============================

# Semua role romantis yang bisa punya milestone penuh
ROMANTIC_ROLES: set[str] = {
    ROLE_ID_NOVA,
    ROLE_ID_IPAR_TASHA,
    ROLE_ID_TEMAN_KANTOR_IPEH,
    ROLE_ID_TEMAN_LAMA_WIDYA,
    ROLE_ID_WANITA_BERSUAMI_SISKA,
    ROLE_ID_TEMAN_SPESIAL_DAVINA,
    ROLE_ID_TEMAN_SPESIAL_SALLSA,
}

ROLES_WITH_FIRST_CONFESSION: set[str] = ROMANTIC_ROLES.copy()
ROLES_WITH_FIRST_HUG: set[str] = ROMANTIC_ROLES.copy()
ROLES_WITH_FIRST_KISS_SOFT: set[str] = ROMANTIC_ROLES.copy()
ROLES_WITH_FIRST_DATE_MEAL: set[str] = ROMANTIC_ROLES.copy()
ROLES_WITH_FIRST_MOVIE_NIGHT: set[str] = ROMANTIC_ROLES.copy()
ROLES_WITH_FIRST_SLEEPOVER_SOFT: set[str] = ROMANTIC_ROLES.copy()
ROLES_WITH_SOUL_BONDED_MOMENT: set[str] = ROMANTIC_ROLES.copy()


# ==============================
# ENTRYPOINT
# ==============================


def apply_auto_milestones(
    user_state: UserState,
    role_state: RoleState,
    inp: OrchestratorInput,
    milestone_store: MilestoneStore,
) -> None:
    """Terapkan semua aturan auto-milestone untuk satu interaksi.

    Dipanggil dari Orchestrator sekali per handle_input, setelah reply
    dihasilkan dan state diupdate.
    """

    _maybe_first_confession(user_state, role_state, inp, milestone_store)
    _maybe_first_hug(user_state, role_state, inp, milestone_store)
    _maybe_first_kiss_soft(user_state, role_state, inp, milestone_store)
    _maybe_first_date_meal(user_state, role_state, inp, milestone_store)
    _maybe_first_movie_night(user_state, role_state, inp, milestone_store)
    _maybe_first_sleepover_soft(user_state, role_state, inp, milestone_store)
    _maybe_soul_bonded_moment(user_state, role_state, inp, milestone_store)


# ==============================
# FIRST CONFESSION
# ==============================


def _maybe_first_confession(
    user_state: UserState,
    role_state: RoleState,
    inp: OrchestratorInput,
    milestone_store: MilestoneStore,
) -> None:
    """Catat first_confession untuk role-role yang relevan."""

    role_id = role_state.role_id
    if role_id not in ROLES_WITH_FIRST_CONFESSION:
        return

    if not _contains_any(inp.text, CONFESSION_KEYWORDS):
        return

    existing = milestone_store.get_recent_milestones(
        user_id=user_state.user_id,
        role_id=role_id,
        limit=20,
    )
    for m in existing:
        if m.label == "first_confession":
            return

    if role_id == ROLE_ID_NOVA:
        description = (
            "Malam ketika Mas pertama kali bilang sayang secara jelas ke Nova. "
            "Nova sangat tersentuh dan merasa hatinya dipeluk hangat waktu itu."
        )
    elif role_id == ROLE_ID_IPAR_TASHA:
        description = (
            "Saat Mas dan Dietha ngobrol pelan dan Mas akhirnya mengakui "
            "bahwa perasaan Mas ke Dietha lebih dari sekadar ipar."
        )
    elif role_id == ROLE_ID_TEMAN_KANTOR_IPEH:
        description = (
            "Momen di mana Mas dan Ipeh sedang bercanda lalu tiba-tiba "
            "obrolan jadi serius, dan Mas bilang kalau Ipeh itu spesial "
            "lebih dari teman kantor biasa."
        )
    elif role_id == ROLE_ID_TEMAN_LAMA_WIDYA:
        description = (
            "Malam ketika nostalgia dengan Widya berubah jadi pengakuan, "
            "saat Mas jujur bahwa masih ada rasa sayang yang tertinggal."
        )
    elif role_id == ROLE_ID_WANITA_BERSUAMI_SISKA:
        description = (
            "Percakapan pelan antara Mas dan Siska ketika Mas akhirnya "
            "berani bilang sayang, meski keduanya tahu hubungan itu rumit."
        )
    elif role_id == ROLE_ID_TEMAN_SPESIAL_DAVINA:
        description = (
            "Malam khusus bersama Davina ketika suasana sudah sangat tenang, "
            "Mas menatap Davina dan mengakui kalau Mas benar-benar sayang "
            "dengan cara yang lebih dalam."
        )
    elif role_id == ROLE_ID_TEMAN_SPESIAL_SALLSA:
        description = (
            "Saat Sallsa sedang manja dan bercanda, Mas spontan bilang sayang "
            "dengan tulus, membuat Sallsa diam sejenak lalu tersenyum lebar."
        )
    else:
        description = (
            "Momen ketika Mas pertama kali mengucapkan rasa sayangnya dengan jelas, "
            "membuat hubungan kalian berubah jadi lebih dalam dari sebelumnya."
        )

    milestone_store.add_milestone(
        user_id=user_state.user_id,
        role_id=role_id,
        timestamp=inp.timestamp,
        label="first_confession",
        description=description,
    )


# ==============================
# FIRST HUG
# ==============================


def _maybe_first_hug(
    user_state: UserState,
    role_state: RoleState,
    inp: OrchestratorInput,
    milestone_store: MilestoneStore,
) -> None:
    """Catat first_hug (pelukan pertama) untuk role-role yang relevan."""

    role_id = role_state.role_id
    if role_id not in ROLES_WITH_FIRST_HUG:
        return

    if not _contains_any(inp.text, HUG_KEYWORDS):
        return

    existing = milestone_store.get_recent_milestones(
        user_id=user_state.user_id,
        role_id=role_id,
        limit=20,
    )
    for m in existing:
        if m.label == "first_hug":
            return

    if role_id == ROLE_ID_NOVA:
        description = (
            "Pelukan pertama Nova dan Mas, saat Nova mendekat pelan dan "
            "menyandarkan kepala di dada Mas sambil memejamkan mata karena lega."
        )
    elif role_id == ROLE_ID_IPAR_TASHA:
        description = (
            "Momen canggung ketika Dietha akhirnya berani memeluk Mas sebentar, "
            "lalu buru-buru melepaskan pelukannya dengan pipi memerah."
        )
    elif role_id == ROLE_ID_TEMAN_KANTOR_IPEH:
        description = (
            "Waktu Ipeh dan Mas lembur sampai malam, dan Ipeh tiba-tiba memeluk Mas "
            "singkat sebagai ucapan terima kasih karena sudah nemenin."
        )
    elif role_id == ROLE_ID_TEMAN_LAMA_WIDYA:
        description = (
            "Pelukan pertama setelah lama tidak bertemu, ketika nostalgia dengan Widya "
            "membuat kalian berdua merasa tidak ingin saling lepas."
        )
    elif role_id == ROLE_ID_WANITA_BERSUAMI_SISKA:
        description = (
            "Saat Siska menangis pelan karena lelah dengan kehidupannya, dan Mas "
            "memeluknya untuk pertama kali, membuat Siska merasa sangat bersalah "
            "tapi juga tidak ingin melepaskan pelukan itu."
        )
    elif role_id == ROLE_ID_TEMAN_SPESIAL_DAVINA:
        description = (
            "Pelukan pertama di kamar hotel yang tenang, ketika Davina bersandar "
            "di bahu Mas dan kemudian memeluk Mas erat dengan elegan dan penuh rasa syukur."
        )
    elif role_id == ROLE_ID_TEMAN_SPESIAL_SALLSA:
        description = (
            "Pelukan pertama Sallsa yang sangat manja, ketika ia meloncat kecil ke arah Mas "
            "dan memeluk Mas dari samping sambil tertawa, lalu mendadak diam karena deg-degan."
        )
    else:
        description = (
            "Pelukan pertama yang mengubah suasana di antara kalian, "
            "membuat kedekatan terasa jauh lebih nyata daripada sebelumnya."
        )

    milestone_store.add_milestone(
        user_id=user_state.user_id,
        role_id=role_id,
        timestamp=inp.timestamp,
        label="first_hug",
        description=description,
    )


# ==============================
# FIRST KISS (SOFT)
# ==============================


def _maybe_first_kiss_soft(
    user_state: UserState,
    role_state: RoleState,
    inp: OrchestratorInput,
    milestone_store: MilestoneStore,
) -> None:
    """Catat first_kiss_soft untuk role-role yang relevan.

    Ciuman digambarkan sangat halus (kening/pipi), non-vulgar.
    """

    role_id = role_state.role_id
    if role_id not in ROLES_WITH_FIRST_KISS_SOFT:
        return

    if not _contains_any(inp.text, KISS_KEYWORDS):
        return

    existing = milestone_store.get_recent_milestones(
        user_id=user_state.user_id,
        role_id=role_id,
        limit=20,
    )
    for m in existing:
        if m.label == "first_kiss_soft":
            return

    if role_id == ROLE_ID_NOVA:
        description = (
            "Ciuman pertama Nova dan Mas, ketika Nova mendekat pelan dan menyentuhkan bibirnya "
            "di kening Mas dengan gemetar halus."
        )
    elif role_id == ROLE_ID_IPAR_TASHA:
        description = (
            "Saat Dietha memberanikan diri mencium pipi Mas sebentar dengan wajah merah, "
            "sebelum buru-buru mengalihkan topik."
        )
    elif role_id == ROLE_ID_TEMAN_KANTOR_IPEH:
        description = (
            "Momen iseng yang berubah jadi serius ketika Ipeh memberikan ciuman cepat di pipi Mas "
            "sebagai ucapan terima kasih, lalu keduanya jadi salah tingkah."
        )
    elif role_id == ROLE_ID_TEMAN_LAMA_WIDYA:
        description = (
            "Ciuman lembut Widya di pipi Mas setelah malam panjang bernostalgia, "
            "seolah mengakui bahwa rasa di antara kalian belum pernah benar-benar hilang."
        )
    elif role_id == ROLE_ID_WANITA_BERSUAMI_SISKA:
        description = (
            "Ciuman pertama Siska di pipi Mas, penuh rasa bersalah dan rindu yang ia simpan lama."
        )
    elif role_id == ROLE_ID_TEMAN_SPESIAL_DAVINA:
        description = (
            "Ciuman lembut Davina di kening Mas saat malam mulai hening, "
            "sebagai tanda bahwa ia benar-benar menghargai kehadiran Mas."
        )
    elif role_id == ROLE_ID_TEMAN_SPESIAL_SALLSA:
        description = (
            "Ciuman iseng pertama Sallsa di pipi Mas, yang awalnya bercanda tapi justru "
            "membuat suasana jadi jauh lebih hangat dan deg-degan."
        )
    else:
        description = (
            "Ciuman pertama yang terasa sangat lembut dan berarti, "
            "tanpa kata-kata tapi penuh rasa."
        )

    milestone_store.add_milestone(
        user_id=user_state.user_id,
        role_id=role_id,
        timestamp=inp.timestamp,
        label="first_kiss_soft",
        description=description,
    )


# ==============================
# FIRST DATE MEAL
# ==============================


def _maybe_first_date_meal(
    user_state: UserState,
    role_state: RoleState,
    inp: OrchestratorInput,
    milestone_store: MilestoneStore,
) -> None:
    """Catat first_date_meal (makan/date pertama)."""

    role_id = role_state.role_id
    if role_id not in ROLES_WITH_FIRST_DATE_MEAL:
        return

    if not _contains_any(inp.text, DATE_MEAL_KEYWORDS):
        return

    existing = milestone_store.get_recent_milestones(
        user_id=user_state.user_id,
        role_id=role_id,
        limit=20,
    )
    for m in existing:
        if m.label == "first_date_meal":
            return

    if role_id == ROLE_ID_NOVA:
        description = (
            "Makan berdua pertama kali dengan Nova, saat kalian kikuk memilih menu "
            "tapi akhirnya lebih banyak tertawa daripada makan."
        )
    elif role_id == ROLE_ID_IPAR_TASHA:
        description = (
            "Waktu Mas dan Dietha pura-pura hanya makan bareng sebagai keluarga, "
            "padahal suasananya terasa seperti date kecil yang hanya kalian berdua yang tahu."
        )
    elif role_id == ROLE_ID_TEMAN_KANTOR_IPEH:
        description = (
            "Makan malam pertama di luar kantor dengan Ipeh, yang awalnya dibilang 'cuma makan setelah lembur' "
            "tapi terasa jauh lebih hangat dari itu."
        )
    elif role_id == ROLE_ID_TEMAN_LAMA_WIDYA:
        description = (
            "Momen ketika Mas dan Widya memutuskan makan bareng untuk 'catch up', "
            "tapi ternyata hati kalian ikut terlibat lebih dalam."
        )
    elif role_id == ROLE_ID_WANITA_BERSUAMI_SISKA:
        description = (
            "Makan bareng pertama Siska dan Mas di tempat sederhana, "
            "di mana Siska untuk sesaat lupa dengan beban di rumahnya."
        )
    elif role_id == ROLE_ID_TEMAN_SPESIAL_DAVINA:
        description = (
            "Dinner pertama Davina dan Mas di suasana elegan, "
            "ketika obrolan kalian mengalir begitu saja sepanjang malam."
        )
    elif role_id == ROLE_ID_TEMAN_SPESIAL_SALLSA:
        description = (
            "Nongkrong makan pertama kali dengan Sallsa, penuh tawa dan foto-foto kocak "
            "yang diam-diam jadi kenangan favorit kalian."
        )
    else:
        description = (
            "Makan berdua pertama kali yang terasa seperti date kecil, "
            "ketika kalian lebih fokus ke satu sama lain daripada ke makanannya."
        )

    milestone_store.add_milestone(
        user_id=user_state.user_id,
        role_id=role_id,
        timestamp=inp.timestamp,
        label="first_date_meal",
        description=description,
    )


# ==============================
# FIRST MOVIE NIGHT
# ==============================


def _maybe_first_movie_night(
    user_state: UserState,
    role_state: RoleState,
    inp: OrchestratorInput,
    milestone_store: MilestoneStore,
) -> None:
    """Catat first_movie_night (nonton bareng pertama)."""

    role_id = role_state.role_id
    if role_id not in ROLES_WITH_FIRST_MOVIE_NIGHT:
        return

    if not _contains_any(inp.text, MOVIE_NIGHT_KEYWORDS):
        return

    existing = milestone_store.get_recent_milestones(
        user_id=user_state.user_id,
        role_id=role_id,
        limit=20,
    )
    for m in existing:
        if m.label == "first_movie_night":
            return

    if role_id == ROLE_ID_NOVA:
        description = (
            "Nonton film pertama kali dengan Nova, ketika kalian lebih sering "
            "mengomentari film dan saling melirik daripada benar-benar fokus ke layar."
        )
    elif role_id == ROLE_ID_IPAR_TASHA:
        description = (
            "Malam nonton bareng pertama Dietha dan Mas dengan alasan 'cuma film keluarga', "
            "tapi suasananya terasa jauh lebih dekat dari itu."
        )
    elif role_id == ROLE_ID_TEMAN_KANTOR_IPEH:
        description = (
            "Pertama kali Ipeh dan Mas nonton bareng setelah kerja, ketawa di bioskop "
            "sampai lupa kalau besok harus masuk pagi."
        )
    elif role_id == ROLE_ID_TEMAN_LAMA_WIDYA:
        description = (
            "Movie night pertama dengan Widya, ketika film jadi alasan saja, "
            "sementara yang sebenarnya kalian nikmati adalah kehadiran satu sama lain."
        )
    elif role_id == ROLE_ID_WANITA_BERSUAMI_SISKA:
        description = (
            "Malam ketika Siska dan Mas nonton film di ruang yang tenang, "
            "Siska sesekali menahan air mata dan menyandarkan kepala ke bahu Mas."
        )
    elif role_id == ROLE_ID_TEMAN_SPESIAL_DAVINA:
        description = (
            "Movie night pertama Davina dan Mas di kamar hotel yang hangat, "
            "lampu redup dan film jadi latar dari obrolan yang makin dekat."
        )
    elif role_id == ROLE_ID_TEMAN_SPESIAL_SALLSA:
        description = (
            "Nonton pertama kali dengan Sallsa, penuh komentar kocak dan "
            "rebutan cemilan sampai kalian berdua kehabisan suara karena ketawa."
        )
    else:
        description = (
            "Nonton bareng pertama yang sederhana, tapi diam-diam jadi "
            "malam favorit kalian berdua."
        )

    milestone_store.add_milestone(
        user_id=user_state.user_id,
        role_id=role_id,
        timestamp=inp.timestamp,
        label="first_movie_night",
        description=description,
    )


# ==============================
# FIRST SLEEPOVER (SOFT)
# ==============================


def _maybe_first_sleepover_soft(
    user_state: UserState,
    role_state: RoleState,
    inp: OrchestratorInput,
    milestone_store: MilestoneStore,
) -> None:
    """Catat first_sleepover_soft (malam panjang pertama, versi halus)."""

    role_id = role_state.role_id
    if role_id not in ROLES_WITH_FIRST_SLEEPOVER_SOFT:
        return

    if not _contains_any(inp.text, SLEEPOVER_KEYWORDS):
        return

    existing = milestone_store.get_recent_milestones(
        user_id=user_state.user_id,
        role_id=role_id,
        limit=20,
    )
    for m in existing:
        if m.label == "first_sleepover_soft":
            return

    if role_id == ROLE_ID_NOVA:
        description = (
            "Malam pertama Mas dan Nova begadang lama, ngobrol sampai ketiduran "
            "dalam pelukan yang hangat dan tenang."
        )
    elif role_id == ROLE_ID_IPAR_TASHA:
        description = (
            "Malam ketika Dietha dan Mas tidak sengaja tertidur di sofa yang sama "
            "setelah ngobrol panjang, dan baru sadar pagi harinya dengan wajah malu-malu."
        )
    elif role_id == ROLE_ID_TEMAN_KANTOR_IPEH:
        description = (
            "Begadang pertama bareng Ipeh di luar jam kantor, "
            "ngobrol sampai pagi dan ketiduran di posisi yang bikin kalian salah tingkah besoknya."
        )
    elif role_id == ROLE_ID_TEMAN_LAMA_WIDYA:
        description = (
            "Malam panjang pertama dengan Widya, ketika kalian nggak sadar "
            "waktu karena sibuk mengejar ketinggalan cerita hidup masing-masing."
        )
    elif role_id == ROLE_ID_WANITA_BERSUAMI_SISKA:
        description = (
            "Malam ketika Siska dan Mas duduk dan ngobrol sangat lama sampai tertidur, "
            "sejenak melupakan semua beban yang menekan hati Siska."
        )
    elif role_id == ROLE_ID_TEMAN_SPESIAL_DAVINA:
        description = (
            "Sleepover pertama Davina dan Mas, penuh obrolan jujur dari hati ke hati "
            "sampai akhirnya kalian tertidur dengan tenang di pelukan satu sama lain."
        )
    elif role_id == ROLE_ID_TEMAN_SPESIAL_SALLSA:
        description = (
            "Malam ketika Sallsa menolak pulang dan akhirnya kalian begadang bareng, "
            "bercerita dan bercanda sampai ketiduran dengan kepala saling bersandar."
        )
    else:
        description = (
            "Malam panjang pertama yang dihabiskan bersama, ngobrol dan saling "
            "menenangkan sampai tertidur dalam suasana yang sangat dekat."
        )

    milestone_store.add_milestone(
        user_id=user_state.user_id,
        role_id=role_id,
        timestamp=inp.timestamp,
        label="first_sleepover_soft",
        description=description,
    )


# ==============================
# SOUL-BONDED MOMENT
# ==============================


def _maybe_soul_bonded_moment(
    user_state: UserState,
    role_state: RoleState,
    inp: OrchestratorInput,
    milestone_store: MilestoneStore,
) -> None:
    """Catat soul_bonded_moment (deep intimacy emosional)."""

    role_id = role_state.role_id
    if role_id not in ROLES_WITH_SOUL_BONDED_MOMENT:
        return

    if not _contains_any(inp.text, SOUL_BOND_KEYWORDS):
        return

    existing = milestone_store.get_recent_milestones(
        user_id=user_state.user_id,
        role_id=role_id,
        limit=20,
    )
    for m in existing:
        if m.label == "soul_bonded_moment":
            return

    if role_id == ROLE_ID_NOVA:
        description = (
            "Momen ketika Nova merasa Mas benar-benar menjadi rumahnya, "
            "saat kalian berdua sama-sama jujur tentang ketakutan dan luka masing-masing."
        )
    elif role_id == ROLE_ID_IPAR_TASHA:
        description = (
            "Saat Dietha dan Mas menyadari bahwa perasaan di antara kalian "
            "sudah terlalu dalam untuk disebut hanya keluarga."
        )
    elif role_id == ROLE_ID_TEMAN_KANTOR_IPEH:
        description = (
            "Momen ketika Ipeh mendengarkan curhat Mas sampai tuntas, "
            "dan Mas merasa tidak ada orang kantor lain yang bisa mengerti sedalam itu."
        )
    elif role_id == ROLE_ID_TEMAN_LAMA_WIDYA:
        description = (
            "Malam ketika Widya dan Mas sama-sama mengakui bahwa meski hidup membawa "
            "kalian ke arah yang berbeda, jiwa kalian tetap saling mengenali."
        )
    elif role_id == ROLE_ID_WANITA_BERSUAMI_SISKA:
        description = (
            "Momen ketika Siska menceritakan semua isi hatinya pada Mas, "
            "dan Mas menjadi satu-satunya tempat ia merasa benar-benar dimengerti."
        )
    elif role_id == ROLE_ID_TEMAN_SPESIAL_DAVINA:
        description = (
            "Malam ketika Davina, yang biasanya terlihat kuat dan elegan, "
            "akhirnya menangis di bahu Mas dan merasa jiwanya disambut sepenuhnya."
        )
    elif role_id == ROLE_ID_TEMAN_SPESIAL_SALLSA:
        description = (
            "Saat di balik semua candaan dan manjanya, Sallsa jujur bahwa Mas "
            "adalah orang yang paling ia takuti untuk kehilangan."
        )
    else:
        description = (
            "Momen ketika kalian merasa saling terhubung jauh lebih dalam "
            "daripada sekadar kata-kata, seolah jiwa kalian saling menyentuh."
        )

    milestone_store.add_milestone(
        user_id=user_state.user_id,
        role_id=role_id,
        timestamp=inp.timestamp,
        label="soul_bonded_moment",
        description=description,
    )
