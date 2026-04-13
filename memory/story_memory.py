"""Story-aware memory untuk menjaga alur cerita tetap konsisten.

Menyimpan ringkasan adegan, plot points, dan perkembangan karakter
agar role bisa merespon sesuai dengan alur cerita yang sudah dibangun.

CARA PAKAI:
1. Copy file ini ke folder memory/
2. Di orchestrator, import dan inject ke __init__
3. Panggil get_story_prompt() saat build prompt
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from threading import RLock
from enum import Enum
import time


class StoryBeat(Enum):
    """Momen penting dalam alur cerita"""
    FIRST_MEET = "first_meet"           # pertama kali ketemu
    FIRST_FLIRT = "first_flirt"         # pertama kali flirting
    FIRST_KISS = "first_kiss"           # pertama kali ciuman
    FIRST_INTIMATE = "first_intimate"   # pertama kali intim
    CONFESSION = "confession"           # pengakuan perasaan
    FIGHT = "fight"                     # konflik/bertengkar
    MAKEOUT = "makeout"                 # making out
    CLIMAX = "climax"                   # climax
    AFTERCARE = "aftercare"             # setelah intim
    PROMISE = "promise"                 # janji/komitmen
    JEALOUSY = "jealousy"               # cemburu
    FAREWELL = "farewell"               # perpisahan


@dataclass
class StoryContext:
    """Konteks cerita untuk satu user-role"""
    user_id: str
    role_id: str
    
    # Alur cerita
    story_beats: List[StoryBeat] = field(default_factory=list)
    current_arc: str = "introduction"  # introduction, building, intimacy, climax, resolution
    pending_actions: List[str] = field(default_factory=list)
    
    # Lokasi & suasana dalam cerita
    story_location: str = ""
    story_vibe: str = "natural"  # romantic, playful, tense, sad, hot
    
    # Ringkasan adegan terakhir
    last_scene_summary: str = ""
    last_scene_timestamp: float = 0.0
    
    # Plot points yang sudah terjadi
    plot_milestones: List[str] = field(default_factory=list)
    
    # Janji/komitmen yang sudah dibuat
    promises: List[str] = field(default_factory=list)
    
    # Nama panggilan yang sudah digunakan
    nicknames_used: List[str] = field(default_factory=list)


class StoryMemoryStore:
    """Menyimpan konteks cerita per user-role - THREAD SAFE"""
    
    def __init__(self):
        self._lock = RLock()
        self._data: Dict[tuple[str, str], StoryContext] = {}
    
    def get_or_create(self, user_id: str, role_id: str) -> StoryContext:
        """Ambil atau buat story context baru untuk user-role pair"""
        key = (user_id, role_id)
        with self._lock:
            if key not in self._data:
                self._data[key] = StoryContext(
                    user_id=user_id,
                    role_id=role_id,
                    story_location="",
                    story_vibe="natural"
                )
            return self._data[key]
    
    def add_story_beat(self, user_id: str, role_id: str, beat: StoryBeat, context: str = "") -> bool:
        """Catat momen penting dalam cerita. Return True jika beat baru ditambahkan."""
        story = self.get_or_create(user_id, role_id)
        with self._lock:
            if beat not in story.story_beats:
                story.story_beats.append(beat)
                timestamp = time.strftime("%H:%M")
                milestone = f"[{timestamp}] {beat.value}: {context[:100] if context else 'Terjadi momen penting'}"
                story.plot_milestones.append(milestone)
                
                # Update arc berdasarkan beat
                if beat in [StoryBeat.FIRST_KISS, StoryBeat.FIRST_INTIMATE]:
                    story.current_arc = "intimacy"
                elif beat == StoryBeat.CLIMAX:
                    story.current_arc = "climax"
                elif beat == StoryBeat.FIGHT:
                    story.current_arc = "tension"
                elif beat == StoryBeat.AFTERCARE:
                    story.current_arc = "resolution"
                
                return True
            return False
    
    def update_scene_summary(self, user_id: str, role_id: str, summary: str):
        """Update ringkasan adegan terakhir"""
        story = self.get_or_create(user_id, role_id)
        with self._lock:
            story.last_scene_summary = summary[:500]
            story.last_scene_timestamp = time.time()
    
    def update_location(self, user_id: str, role_id: str, location: str):
        """Update lokasi dalam cerita"""
        story = self.get_or_create(user_id, role_id)
        with self._lock:
            story.story_location = location
    
    def update_vibe(self, user_id: str, role_id: str, vibe: str):
        """Update suasana cerita"""
        valid_vibes = ["romantic", "playful", "tense", "sad", "hot", "natural"]
        if vibe in valid_vibes:
            story = self.get_or_create(user_id, role_id)
            with self._lock:
                story.story_vibe = vibe
    
    def add_promise(self, user_id: str, role_id: str, promise: str):
        """Catat janji/komitmen yang dibuat"""
        story = self.get_or_create(user_id, role_id)
        with self._lock:
            if promise not in story.promises:
                story.promises.append(promise)
    
    def add_pending_action(self, user_id: str, role_id: str, action: str):
        """Tandai aksi yang belum selesai"""
        story = self.get_or_create(user_id, role_id)
        with self._lock:
            if action not in story.pending_actions:
                story.pending_actions.append(action)
    
    def clear_pending_actions(self, user_id: str, role_id: str):
        """Bersihkan semua aksi pending"""
        story = self.get_or_create(user_id, role_id)
        with self._lock:
            story.pending_actions.clear()
    
    def add_nickname(self, user_id: str, role_id: str, nickname: str):
        """Catat nama panggilan yang sudah digunakan"""
        story = self.get_or_create(user_id, role_id)
        with self._lock:
            if nickname not in story.nicknames_used:
                story.nicknames_used.append(nickname)
    
    def get_story_prompt(self, user_id: str, role_id: str) -> str:
        """Buat prompt konteks cerita untuk LLM (siap pakai)"""
        story = self.get_or_create(user_id, role_id)
        
        # Jika belum ada cerita
        if not story.story_beats and not story.plot_milestones:
            return """
📖 ALUR CERITA: Ini adalah awal pertemuan kalian. Belum ada kenangan atau momen spesial sebelumnya.
→ Bersikaplah seperti baru pertama kali berinteraksi atau masih dalam tahap pengenalan.
"""
        
        # Bangun narasi dari plot milestones (ambil 5 terakhir)
        recent_milestones = story.plot_milestones[-5:] if story.plot_milestones else []
        
        # Bangun string pending actions
        pending_str = ""
        if story.pending_actions:
            pending_str = f"\n⏳ AKSI YANG BELUM SELESAI: {', '.join(story.pending_actions)}"
        
        # Bangun string promises
        promises_str = ""
        if story.promises:
            promises_str = f"\n📜 JANJI YANG SUDAH DIBUAT: {', '.join(story.promises)}"
        
        # Bangun string nicknames
        nicknames_str = ""
        if story.nicknames_used:
            nicknames_str = f"\n💕 NAMA PANGGILAN YANG SUDAH DIPAKAI: {', '.join(story.nicknames_used)}"
        
        prompt = f"""
═══════════════════════════════════════════════════════════════
📖 KONTEKS CERITA (WAJIB DIIKUTI UNTUK KONSISTENSI!)
═══════════════════════════════════════════════════════════════

📍 ARC CERITA SAAT INI: {story.current_arc}
🎭 SUASANA: {story.story_vibe}
🗺️ LOKASI: {story.story_location or 'Masih di tempat sebelumnya'}

📜 MOMEN PENTING YANG SUDAH TERJADI:
{chr(10).join(f'  • {m}' for m in recent_milestones) if recent_milestones else '  • Belum ada momen penting yang tercatat'}

🎬 ADEGAN TERAKHIR:
{story.last_scene_summary or 'Adegan baru dimulai, belum ada riwayat'}

{pending_str}
{promises_str}
{nicknames_str}

═══════════════════════════════════════════════════════════════
🎯 ATURAN KONTINUITAS CERITA:
═══════════════════════════════════════════════════════════════

1. JANGAN RESTART CERITA!
   - Kalau sudah pernah bilang "sayang", jangan bertingkah seperti baru kenal
   - Kalau sudah pernah intim, jangan tanya "Mas mau apa?"
   - Kalau sudah pernah janji, INGAT dan patuhi janjinya!

2. REFERENSI MOMEN SEBELUMNYA (bikin natural):
   - "Mas masih ingat waktu kita..."
   - "Seperti kemarin ya, Mas..."
   - "Lain dari biasanya, Mas..."

3. JANGAN ULANGI ADEGAN YANG SAMA:
   - Jika sudah lewat fase malu-malu, jangan balik malu-malu lagi
   - Kembangkan cerita ke arah yang baru

4. IKUTI ARC CERITA:
   - Jika arc = "intimacy" → fokus ke kedekatan fisik & emosional
   - Jika arc = "climax" → fokus ke puncak kenikmatan
   - Jika arc = "resolution" → suasana tenang, hangat, aftercare

═══════════════════════════════════════════════════════════════
"""
        return prompt
    
    def reset_story(self, user_id: str, role_id: str):
        """Reset semua cerita (hati-hati, ini akan menghapus semua progress)"""
        key = (user_id, role_id)
        with self._lock:
            if key in self._data:
                del self._data[key]
    
    def get_summary_for_admin(self, user_id: str, role_id: str) -> dict:
        """Dapatkan ringkasan untuk keperluan admin/debug"""
        story = self.get_or_create(user_id, role_id)
        return {
            "user_id": user_id,
            "role_id": role_id,
            "current_arc": story.current_arc,
            "story_vibe": story.story_vibe,
            "story_location": story.story_location,
            "total_beats": len(story.story_beats),
            "total_milestones": len(story.plot_milestones),
            "total_promises": len(story.promises),
            "last_scene": story.last_scene_summary[:100] if story.last_scene_summary else None,
        }
