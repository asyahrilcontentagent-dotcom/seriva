# Dockerfile untuk SERIVA (Telegram bot + LLM client)

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Matikan bytecode dan buffer stdout (lebih enak untuk log)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install sistem dependency minimal (jika butuh)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Salin requirements jika ada, atau install langsung dependency utama
# Kalau kamu punya requirements.txt sendiri, ganti bagian ini.

# Contoh minimal requirements langsung:
#   python-telegram-bot, requests

RUN pip install --no-cache-dir \
    python-telegram-bot==20.7 \
    requests

# Salin seluruh project ke dalam container
COPY . /app

# Default command: jalankan bot Telegram
CMD ["python", "-m", "bot.main"]
