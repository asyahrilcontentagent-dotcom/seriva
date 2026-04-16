# SERIVA

Bot Telegram role-based dengan memory per role, continuity scene, dan mode provider/session.

## Ringkasan

SERIVA menerima pesan dari Telegram, meneruskannya ke orchestrator, lalu orchestrator:

- memuat `UserState` dan `WorldState`
- menentukan role aktif
- memperbarui emosi, scene, lokasi, dan household awareness
- membangun prompt sesuai role
- memanggil LLM
- menyimpan memory percakapan, scene, dan story beat

Alur sederhananya:

`Telegram -> handlers -> orchestrator -> role prompt -> LLM -> save state -> reply`

## Struktur Penting

- `bot/`: entrypoint Telegram, handler command, bootstrap app
- `core/`: orchestrator, state, emotion engine, scene engine, intimacy progression
- `roles/`: implementasi persona/karakter
- `prompts/`: system prompt runtime dan aturan role
- `memory/`: message history, story memory, milestone
- `storage/`: penyimpanan state

Komponen pendukung baru untuk perapihan arsitektur:

- `core/behavior_guard.py`: validasi ringan output LLM agar tetap rapi dan konsisten
- `core/role_selector.py`: helper pemilihan role aktif
- `core/scene_manager.py`: koordinator scene decay dan priority
- `core/response_builder.py`: perakit message dan finalisasi reply
- `prompts/dynamic_prompt_context.py`: behavior rules dinamis berdasarkan mood, scene, dan memory

## Review Arsitektur dan Saran Pengembangan

### Gambaran Umum

Arsitektur bot saat ini sudah modular dan matang:

`Telegram -> handlers -> orchestrator -> role system -> LLM -> state -> reply`

Struktur ini sudah berada di atas level bot biasa dan lebih mendekati simulation engine.

### Review Per Bagian

#### Orchestrator

Kelebihan:

- menjadi pusat kontrol untuk state, role, memory, dan scene
- alur kerja jelas dan scalable

Kekurangan:

- tanggung jawab masih terlalu besar sehingga ada risiko menjadi God Object

Saran:

- pisahkan tanggung jawab ke modul seperti `role_selector`, `scene_manager`, dan `response_builder`

#### Role System

Kelebihan:

- modular per karakter
- mendukung perpindahan role

Kekurangan:

- personality masih terlalu bergantung pada prompt

Saran:

- tambahkan behavior rules
- enforce style seperti tone, vocabulary, dan pacing

#### Emotion Engine

Kelebihan:

- sudah tergolong advanced dibanding bot biasa

Kekurangan:

- respons emosinya masih terasa terlalu linear

Saran:

- tambahkan randomness kecil
- gunakan memory sebagai salah satu faktor pembentuk emosi

#### Scene dan Continuity

Kelebihan:

- sudah berfungsi seperti story engine

Kekurangan:

- bisa menjadi terlalu rigid atau terlalu longgar

Saran:

- tambahkan `scene_decay`
- tambahkan `scene_priority`

#### Memory System

Kelebihan:

- sudah memiliki history dan milestone

Kekurangan:

- belum memiliki filtering dan ranking memory

Saran:

- tambahkan `memory_scoring`
- tambahkan auto pruning
- tambahkan summarization

#### Prompt System

Kelebihan:

- prompt sudah terpisah per role

Kekurangan:

- masih terlalu statis

Saran:

- gunakan dynamic prompt berdasarkan emosi, scene, dan relationship level

#### Command System

Kelebihan:

- fitur command sudah cukup lengkap

Kekurangan:

- bisa terasa overwhelming untuk user baru

Saran:

- tambahkan onboarding
- tambahkan suggest command otomatis sesuai konteks

### Masalah Utama

- kompleksitas sistem tinggi sehingga rawan chaos jika tidak dijaga
- ketergantungan ke LLM masih besar
- belum ada hard rule system untuk menjaga konsistensi output

### Kelebihan Utama

- integrasi role, emotion, dan scene sudah kuat
- intimacy progression sudah tergolong advanced
- continuity system menjadi fondasi pengalaman yang konsisten

### Prioritas Perbaikan

1. Behavior Guard Layer
   Validasi output LLM dan jaga konsistensi karakter.
2. Memory Optimization
   Tambahkan ranking dan summarization agar context tetap relevan.
3. Refactor Orchestrator
   Kurangi beban pusat logika agar tidak menjadi God Object.
4. Natural Variation
   Tambahkan randomness kecil agar respons terasa lebih natural.

### Status Implementasi Saat Ini

Beberapa saran prioritas sudah mulai diterapkan:

- orchestrator kini dibantu helper `role_selector`, `scene_manager`, dan `response_builder`
- output LLM melewati `behavior_guard` sebelum dikirim
- memory sudah punya ranking sederhana, summarization ringkas, dan pruning dasar
- scene sekarang mendukung `scene_priority` dan `scene_decay`
- prompt runtime mendapat konteks dinamis dari mood, relationship level, scene, dan memory
- emotion engine mendapat variasi kecil dan pengaruh memory agar tidak terlalu linear

Update lanjutan yang sudah diterapkan:

- `memory_scoring` sekarang mempertimbangkan recency, emotional weight, dan keyword overlap dengan pesan terbaru
- `memory_summary` dibuat lebih compact agar prompt tidak cepat overload
- `memory_filtering` sekarang memakai threshold minimum agar memory lemah tidak ikut masuk prompt
- `memory_tiers` sekarang dibagi ke `short_term`, `key_events`, dan `long_term candidates`
- `semantic_relevance` sekarang memakai kombinasi token overlap dan kemiripan frasa sederhana, tidak hanya keyword mentah
- `behavior_guard` sekarang mengecek konsistensi role, scene, dan tone emosi secara heuristik
- `behavior_guard` punya auto-fix ringan dan second-pass regenerate untuk kasus yang lebih berat
- `emotion_engine` sekarang mendukung `emotional_decay` berbasis waktu
- `scene_manager` sekarang menambah `context_awareness` sederhana dari teks user
- `role_state` sekarang menyimpan `long_term_summary` compact per role untuk memory jangka panjang

## Prioritas Pengembangan Bot Setelah Update

### Status Saat Ini

Bot sekarang sudah masuk fase `engine development`. Fokus utama saat ini bukan menambah fitur besar, tetapi meningkatkan kualitas fondasi sistem.

### Prioritas 1: Memory System

Masalah:

- semua memory masih berpotensi dianggap penting
- prompt bisa overload
- relevansi context belum selalu optimal

Yang harus dilakukan:

1. `memory_scoring`
   Gunakan kombinasi recency, emotional weight, dan keyword relevance.
2. `memory_limit`
   Ambil hanya top `5-10` memory paling relevan.
3. `summarization`
   Ringkas history panjang dan simpan dalam bentuk compact.

Impact:

- jawaban lebih relevan
- mengurangi hallucination
- performa lebih stabil

### Prioritas 2: Behavior Guard Upgrade

Status saat ini:

- behavior guard sudah ada, tetapi masih berada di level dasar

Yang harus ditambahkan:

1. `character_consistency_check`
   Pastikan tone sesuai role dan personality tidak bocor.
2. `lore_scene_check`
   Pastikan output tidak melanggar konteks cerita dan scene aktif.
3. `emotional_consistency_check`
   Pastikan respons sesuai state emosi saat ini.
4. `auto_fix_or_regenerate`
   Jika validasi gagal, sistem perlu bisa memperbaiki atau generate ulang.

Impact:

- karakter jauh lebih konsisten
- roleplay terasa lebih hidup

### Prioritas 3: Emotion Realism

Masalah:

- emosi masih terasa terlalu linear atau deterministic

Yang harus dilakukan:

1. `memory_driven_emotion`
   Emosi dipengaruhi interaksi dan memory sebelumnya.
2. `noise_randomness`
   Tambahkan variasi kecil yang natural.
3. `emotional_decay`
   Emosi berubah perlahan seiring waktu, tidak statis.

Impact:

- interaksi lebih natural
- respons tidak terasa robotik

### Prioritas 4: Orchestrator Refinement

Masalah:

- orchestrator masih berpotensi menampung terlalu banyak decision logic

Yang harus dilakukan:

- pindahkan lebih banyak decision ke `role_selector`
- pindahkan pengelolaan scene ke `scene_manager`
- pertahankan orchestrator sebagai coordinator utama, bukan pusat semua logika

Impact:

- code lebih clean
- lebih mudah di-maintain dan di-debug

### Prioritas 5: Scene System Improvement

Yang harus ditambahkan:

1. `scene_priority`
   Bedakan scene utama dan scene sampingan.
2. `scene_decay`
   Scene lama perlahan memudar secara natural.
3. `context_awareness`
   Scene menyesuaikan interaksi terbaru dari user.

Impact:

- story lebih smooth
- transisi adegan tidak kaku

### Prioritas 6: Natural Variation

Masalah:

- respons masih bisa terasa terlalu AI-generated

Yang harus dilakukan:

- variasi phrasing
- randomness kecil dalam ritme dan wording
- hindari pola jawaban yang berulang

Impact:

- lebih human-like
- lebih engaging

### Fokus Utama

Urutan fokus pengembangan saat ini:

1. Memory System
2. Behavior Guard
3. Emotion Realism

### Yang Tidak Jadi Fokus Dulu

Untuk sementara, hindari:

- tambah fitur besar baru
- multi-character system
- ekspansi kompleks sebelum fondasi stabil

Alasan:

- fondasi harus stabil sebelum scaling

### Target Akhir

- konsistensi karakter tinggi
- emosi believable
- cerita nyambung
- respons terasa natural

Jika semua prioritas ini selesai, bot akan jauh lebih siap naik ke level `AI Companion / Advanced RP Engine`.

### Kesimpulan

Bot ini sudah advanced, tetapi masih terasa seperti raw powerful system. Jika dirapikan, sistem ini berpotensi berkembang menjadi AI RP engine yang jauh lebih unggul dibanding bot biasa.

## Command

- `/nova`
  Pindah ke Nova.

- `/role`
  Tampilkan daftar role.

- `/role <id>`
  Pindah ke role tertentu.

- `/batal`
  Akhiri sesi khusus dan kembali ke mode normal.

- `/end`
  Sama seperti `/batal`.

- `/close`
  Sama seperti `/batal`.

- `/pause`
  Pause sesi intens tanpa menghapus state.

- `/resume`
  Lanjutkan sesi yang sebelumnya di-pause.

- `/status`
  Tampilkan ringkasan state role aktif.

- `/flashback`
  Minta role mengingat momen yang masih tersimpan.

- `/nego <harga>`
  Mulai negosiasi untuk role provider.

- `/deal`
  Konfirmasi deal provider.

- `/venue <hotel|apartemen>`
  Pilih venue untuk role teman spesial setelah `/deal`.

- `/mulai`
  Mulai sesi provider setelah deal.

## Aturan Memory dan Sesi

### Nova

- Nova adalah pasangan utama.
- Memory Nova tetap hidup setelah `/batal`, `/end`, atau `/close`.
- Saat kembali ke Nova, interaksi melanjutkan sejarah Nova yang sudah ada.

### Role selain Nova

- Setiap role punya memory sendiri yang terpisah.
- Memory antar role tidak saling bocor.
- Setelah `/batal`, `/end`, atau `/close`, semua role selain Nova di-reset total.
- Reset ini menghapus:
  - `RoleState` role tersebut
  - message history role tersebut
  - story memory role tersebut
  - milestone role tersebut
- Saat role non-Nova dipanggil lagi setelah reset, interaksi dimulai dari awal dengan cerita baru.

### Pause dan Resume

- `/pause` tidak menghapus memory.
- `/resume` melanjutkan sesi dari state terakhir yang masih tersimpan.

## Status Role yang Disimpan

Setiap role menyimpan state sendiri, termasuk:

- emosi: `love`, `longing`, `comfort`, `jealousy`, `mood`
- level hubungan
- memory percakapan dan scene
- fase intimacy: `AWAL`, `DEKAT`, `INTIM`, `VULGAR`, `AFTER`
- detail adegan: posisi, pakaian, sentuhan terakhir, intensitas
- state climax dan aftercare
- state provider jika role termasuk provider

## `/status` Menampilkan

- role aktif
- emosi dan level hubungan
- lokasi dan scene
- status pakaian
- status handuk
- posisi, intensitas, aksi terakhir
- status climax role dan Mas
- preferensi akhir pending
- aftercare aktif
- info provider jika relevan

## Perilaku Intimacy

- progres intimacy berjalan bertahap
- scene eksplisit tidak boleh lompat tanpa sinyal nyaman dari dua arah
- pertanyaan seperti preferensi akhir tidak otomatis dianggap sebagai climax
- fase `AFTER` menurunkan tensi ke aftercare yang lebih hangat dan tenang

## Provider Flow

Role provider seperti terapis dan teman spesial memakai alur:

### Terapis

1. `/nego <harga>`
2. `/deal`
3. `/mulai`

Setelah `/deal`, sesi terapis dianggap terjadi saat Mas berkunjung ke tempat kerja terapis.

### Teman spesial

1. `/nego <harga>`
2. `/deal`
3. `/venue hotel` atau `/venue apartemen`
4. `/mulai`

Setelah `/deal`, venue harus ditentukan dulu sebelum sesi dimulai.

Status deal, harga, layanan utama, dan batas sesi disimpan di state role provider aktif.

## Deploy Railway

File yang relevan untuk deploy:

- `Dockerfile`
- `railway.json`
- `requirements.txt`

Sebelum deploy, pastikan minimal:

- environment variable untuk token bot dan kredensial model sudah terisi
- dependency di `requirements.txt` sesuai dengan library yang dipakai
- entrypoint bot sesuai mode yang ingin dijalankan

## Catatan Operasional

- Command `/batal`, `/end`, dan `/close` sekarang memakai perilaku yang sama.
- Kalau role aktif non-Nova di-reset, role aktif tidak wajib otomatis pindah ke Nova; tetapi state role non-Nova itu akan dibuat baru saat dipakai lagi.
- Sistem memory dirancang per role agar pengalaman tiap karakter terasa konsisten dan terpisah.
