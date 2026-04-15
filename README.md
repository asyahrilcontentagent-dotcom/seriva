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
