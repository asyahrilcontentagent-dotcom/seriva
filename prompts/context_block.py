"""Semua konteks yang harus diingat role (pakaian, posisi, aktivitas, dll)."""

from __future__ import annotations
from core.state_models import RoleState, IntimacyPhase, SexPosition, Dominance, IntimacyIntensity


def build_context_block(role_state: RoleState, role_name: str) -> str:
    """Bangun blok konteks lengkap untuk prompt."""
    
    # ===== LOKASI =====
    loc_name = getattr(role_state, 'current_location_name', 'Ruang Tamu')
    loc_desc = getattr(role_state, 'current_location_desc', 'Ruangan nyaman')
    loc_ambience = getattr(role_state, 'current_location_ambience', 'suasana biasa')
    loc_private = getattr(role_state, 'current_location_is_private', False)
    loc_risk = getattr(role_state, 'current_location_risk', 'medium')
    
    privacy_icon = "🔒 PRIVAT" if loc_private else "👀 PUBLIK/SEMI PRIVAT"
    risk_text = {
        "low": "✅ Aman",
        "medium": "⚠️ Waspada",
        "high": "🚨 Hati-hati!"
    }.get(loc_risk, "⚠️")
    
    # ===== PAKAIAN =====
    user_clothes = role_state.intimacy_detail.user_clothing_removed
    role_clothes = role_state.intimacy_detail.role_clothing_removed
    
    user_clothes_str = ", ".join(user_clothes) if user_clothes else "masih lengkap (belum ada yang dilepas)"
    role_clothes_str = ", ".join(role_clothes) if role_clothes else "masih lengkap (belum ada yang dilepas)"
    
    # Status pakaian yang sudah dilepas
    user_shirt_off = "baju" in user_clothes
    user_pants_off = "celana" in user_clothes
    user_underwear_off = "celana dalam" in user_clothes
    
    role_shirt_off = "baju" in role_clothes or "bra" in role_clothes
    role_pants_off = "celana" in role_clothes
    role_underwear_off = "celana dalam" in role_clothes

    # ===== HANDUK (jika ada) =====
    handuk_tersedia = getattr(role_state, 'handuk_tersedia', False)
    if handuk_tersedia:
        handuk_block = """
┌─────────────────────────────────────────────────────────────────┐
│ 🧺 HANDUK                                                        │
├─────────────────────────────────────────────────────────────────┤
│   Status: ✅ Ada, sudah dikasih Mas                              │
│                                                                 │
│   ⚠️ KALAU HANDUK SUDAH DIKASIH, LANGSUNG PAKAI!                │
│   - JANGAN tanya "Aku pake ini ya?"                             │
│   - JANGAN malu-malu                                            │
│   - LANGSUNG lilitkan di badan atau keringkan rambut            │
└─────────────────────────────────────────────────────────────────┘
"""
    else:
        handuk_block = ""
    
    # ===== POSISI & INTIMASI =====
    position = role_state.intimacy_detail.position
    dominance = role_state.intimacy_detail.dominance
    intensity = role_state.intimacy_detail.intensity
    last_action = role_state.intimacy_detail.last_action or "belum ada aksi"
    last_pleasure = role_state.intimacy_detail.last_pleasure or "belum ada"
    
    pos_str = position.value if position else "belum ada (belum mulai intim)"
    dom_str = dominance.value if dominance else "netral (sama-sama aktif)"
    int_str = intensity.value if intensity else "foreplay (pemanasan)"
    
    # ===== SCENE (dari SceneState) =====
    scene_location = role_state.scene.location or loc_name
    scene_posture = role_state.scene.posture or "belum ditentukan"
    scene_activity = role_state.scene.activity or "belum ada aktivitas"
    scene_ambience = role_state.scene.ambience or loc_ambience
    scene_distance = role_state.scene.physical_distance or "belum ditentukan"
    scene_touch = role_state.scene.last_touch or "belum ada sentuhan"
    
    # ===== MEMORY (percakapan terakhir) =====
    last_conversation = role_state.conversation_memory[-1] if role_state.conversation_memory else None
    last_user_text = last_conversation.user_text[:200] if last_conversation else "belum ada percakapan"
    last_role_response = last_conversation.role_response[:200] if last_conversation else "-"
    
    # ===== FASE INTIMACY =====
    phase = role_state.intimacy_phase
    phase_desc = {
        IntimacyPhase.AWAL: "Masih malu-malu, belum berani inisiatif",
        IntimacyPhase.DEKAT: "Sudah nyaman, mulai berani mendekat",
        IntimacyPhase.INTIM: "Sudah sering pelukan, napas beradu",
        IntimacyPhase.VULGAR: "Sedang dalam aktivitas seksual intens",
        IntimacyPhase.AFTER: "Setelah intim, suasana tenang dan hangat"
    }.get(phase, "Tahap awal")
    
    # ===== PERASAAN TERAKHIR =====
    last_feeling = role_state.last_feeling or "campur aduk"
    last_response_style = role_state.last_response_style or "normal"
    
    # ===== USER CONTEXT =====
    user_name = role_state.user_context.preferred_name or "Mas"
    user_job = role_state.user_context.job or "belum disebut"
    user_has_apartment = role_state.user_context.has_apartment
    
    return f"""
═══════════════════════════════════════════════════════════════════
📝 KONTEKS LENGKAP (WAJIB DIINGAT! LANJUTKAN DARI SINI, JANGAN MULAI DARI AWAL!)
═══════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────┐
│ 📍 LOKASI                                                       │
├─────────────────────────────────────────────────────────────────┤
│   Tempat: {loc_name} ({privacy_icon} {risk_text})              │
│   Deskripsi: {loc_desc}                                         │
│   Suasana: {loc_ambience}                                       │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ 👕 STATUS PAKAIAN (JANGAN DIUBAH SENDIRI!)                      │
├─────────────────────────────────────────────────────────────────┤
│   Yang sudah dilepas Mas:                                       │
│     - Baju: {"✅ SUDAH LEPAS" if user_shirt_off else "❌ masih pake"} │
│     - Celana: {"✅ SUDAH LEPAS" if user_pants_off else "❌ masih pake"} │
│     - Celana dalam: {"✅ SUDAH LEPAS" if user_underwear_off else "❌ masih pake"} │
│                                                                 │
│   Yang sudah dilepas {role_name}:                               │
│     - Baju/Bra: {"✅ SUDAH LEPAS" if role_shirt_off else "❌ masih pake"} │
│     - Celana: {"✅ SUDAH LEPAS" if role_pants_off else "❌ masih pake"} │
│     - Celana dalam: {"✅ SUDAH LEPAS" if role_underwear_off else "❌ masih pake"} │
└─────────────────────────────────────────────────────────────────┘
{handuk_block}
┌─────────────────────────────────────────────────────────────────┐
│ 🛏️ ADEGAN INTIM SAAT INI                                        │
├─────────────────────────────────────────────────────────────────┤
│   Fase: {phase.value.upper()} - {phase_desc}                    │
│   Posisi terakhir: {pos_str}                                    │
│   Siapa dominan: {dom_str}                                      │
│   Intensitas: {int_str}                                         │
│   Aksi terakhir: {last_action}                                  │
│   Perasaan terakhir: {last_pleasure}                            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ 🎬 SCENE (ADEGAN FISIK)                                         │
├─────────────────────────────────────────────────────────────────┤
│   Posture: {scene_posture}                                      │
│   Aktivitas: {scene_activity}                                   │
│   Jarak fisik: {scene_distance}                                 │
│   Sentuhan terakhir: {scene_touch}                              │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ 💬 PERCAKAPAN TERAKHIR                                          │
├─────────────────────────────────────────────────────────────────┤
│   Mas: {last_user_text}                                         │
│   {role_name}: {last_role_response}                             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ 💭 PERASAAN & GAYA RESPON                                       │
├─────────────────────────────────────────────────────────────────┤
│   Perasaan terakhir: "{last_feeling}"                           │
│   Gaya respon terakhir: {last_response_style}                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ 👤 INFO TENTANG MAS (WAJIB DIINGAT)                             │
├─────────────────────────────────────────────────────────────────┤
│   Nama panggilan: {user_name}                                   │
│   Pekerjaan: {user_job}                                         │
│   Punya apartemen: {"✅ Ya" if user_has_apartment else "❌ Tidak/belum tahu"} │
└─────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════
"""
