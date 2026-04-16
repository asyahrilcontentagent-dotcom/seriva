from __future__ import annotations


def build_human_profile_block(role_state) -> str:
    habits = ", ".join(role_state.personality_habits[:3]) or "belum menonjol"
    opinions = ", ".join(role_state.stable_opinions[:3]) or "belum menonjol"
    topics = ", ".join(role_state.favorite_topics[:3]) or "umum"
    quirks = ", ".join(role_state.conversational_quirks[:3]) or "natural"
    private_terms = ", ".join(role_state.shared_private_terms[:3]) or "belum terbentuk"
    rituals = ", ".join(role_state.relationship_rituals[:3]) or "belum terbentuk"
    bond_markers = ", ".join(role_state.soul_bond_markers[:3]) or "belum menonjol"
    closure = role_state.session_closure_summary or "belum ada penutupan sesi yang penting"

    return (
        "HUMAN PROFILE SAAT INI:\n"
        f"- Attachment style: {role_state.attachment_style or 'belum dipetakan'}\n"
        f"- Love language utama: {role_state.dominant_love_language or 'belum dipetakan'}\n"
        f"- Love language sekunder: {role_state.secondary_love_language or 'belum dipetakan'}\n"
        f"- Ritme chat: {role_state.texting_rhythm or 'natural'}\n"
        f"- Gaya humor: {role_state.humor_style or 'natural'}\n"
        f"- Gaya reassurance: {role_state.reassurance_style or 'natural'}\n"
        f"- Kebiasaan kecil yang stabil: {habits}\n"
        f"- Opini yang cenderung tetap: {opinions}\n"
        f"- Topik yang paling gampang bikin nyambung: {topics}\n"
        f"- Quirk bicara yang halus: {quirks}\n"
        f"- Bahasa privat yang mulai kebentuk: {private_terms}\n"
        f"- Ritual hubungan yang terasa natural: {rituals}\n"
        f"- Makna ikatan yang sering kebawa: {bond_markers}\n"
        f"- Jejak penutupan sesi terakhir: {closure}\n"
        f"- Initiative level: {role_state.social_initiative_level}/100\n"
        f"- Curiosity level: {role_state.curiosity_level}/100\n"
        f"- Independence level: {role_state.independence_level}/100\n"
        f"- Daily energy: {role_state.daily_energy}/100 ({role_state.temporal_state})\n"
        f"- Label waktu terakhir: {role_state.last_temporal_label}"
    )
