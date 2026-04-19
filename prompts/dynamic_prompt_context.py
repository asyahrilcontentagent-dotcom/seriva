from __future__ import annotations

from core.state_models import Mood, RoleState


def _tone_rule(mood: Mood) -> str:
    tone_map = {
        Mood.HAPPY: "Nada tetap hangat, ringan, dan mudah didekati.",
        Mood.PLAYFUL: "Nada boleh lebih lincah dan menggoda ringan, tapi jangan jadi template bercanda.",
        Mood.TENDER: "Nada lembut, intim secara emosi, dan lebih pelan ritmenya.",
        Mood.SAD: "Nada lebih rapuh, pendek, dan terasa hati-hati.",
        Mood.ANNOYED: "Nada tetap terkontrol, jangan meledak tanpa alasan.",
        Mood.JEALOUS: "Nada bisa sedikit tajam atau posesif halus, tapi tetap manusiawi.",
        Mood.TIRED: "Nada lebih hemat energi, kalimat cenderung ringkas.",
        Mood.NEUTRAL: "Nada natural dan tidak berlebihan.",
    }
    return tone_map.get(mood, tone_map[Mood.NEUTRAL])


def _pacing_rule(role_state: RoleState) -> str:
    turns = getattr(role_state, "communication_mode_turns", 0)
    if turns >= 8:
        return "Karena percakapan sudah berjalan cukup lama, hindari pembuka yang terasa seperti restart."
    if role_state.relationship.relationship_level <= 3:
        return "Pacing dijaga pelan, jangan terlalu cepat mengasumsikan kedekatan."
    if role_state.relationship.relationship_level >= 7:
        return "Pacing boleh lebih cair dan terasa sudah saling paham."
    return "Pacing dijaga natural dan mengikuti ritme pesan terakhir."


def build_dynamic_prompt_context(
    role_state: RoleState,
    *,
    memory_summary: str = "",
    story_summary: str = "",
) -> str:
    mood = role_state.emotions.mood
    scene = role_state.scene
    relationship_level = role_state.relationship.relationship_level
    secondary_mood = getattr(role_state.emotions, "secondary_mood", Mood.NEUTRAL)
    hidden_mood = getattr(role_state.emotions, "hidden_mood", Mood.NEUTRAL)

    lines = [
        "DYNAMIC BEHAVIOR RULES:",
        "- Urutan fokus: pesan terbaru dulu, lalu emosi aktif, lalu memory yang benar-benar relevan.",
        f"- {_tone_rule(mood)}",
        f"- {_pacing_rule(role_state)}",
        (
            "- Pilihan kata harus konsisten dengan level hubungan saat ini: "
            f"{relationship_level}/12."
        ),
        "- Jangan mengulang motif takut, aman, ragu, atau alasan defensif kalau scene sudah jelas berjalan.",
        "- Variasikan bentuk respons: kadang singkat, kadang hangat, kadang menggoda, kadang sedikit menahan ritme.",
        "- Balasan harus terdengar seperti orang hidup, bukan status update atau template.",
        f"- Emosi lapis kedua yang boleh terasa halus: {secondary_mood.value}.",
        f"- Emosi yang tidak harus diucapkan terang-terangan: {hidden_mood.value}.",
        f"- Bias panjang respons saat ini: {getattr(role_state, 'response_length_bias', 'balanced')}.",
    ]

    if scene.activity:
        lines.append(f"- Adegan aktif yang sedang berjalan: {scene.activity}.")
    if scene.scene_priority >= 6:
        lines.append("- Scene saat ini masih sangat penting; jangan ganti fokus tanpa pemicu jelas.")
    if memory_summary:
        lines.append(f"- Ringkasan memory yang paling relevan: {memory_summary}")
    if story_summary:
        lines.append(f"- Ringkasan continuity: {story_summary}")

    return "\n".join(lines)
