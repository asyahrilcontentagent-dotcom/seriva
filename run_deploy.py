import importlib
import os
import sys
from datetime import datetime
from pathlib import Path


# ==============================
# SIMPLE LOGGER
# ==============================


def log(level: str, message: str) -> None:
    """Simple structured logger for deploy runner."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{now} | {level} | SERIVA-DEPLOY | {message}")


# ==============================
# PATH & ENV SETUP
# ==============================


def ensure_root_on_sys_path() -> Path:
    """Pastikan root project (/app di Railway) ada di sys.path."""
    root_dir = Path(__file__).resolve().parent
    log("INFO", f"Project ROOT_DIR: {root_dir}")
    log("INFO", f"Root entries: {[p.name for p in root_dir.iterdir()]}")

    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))
        log("INFO", f"Added {root_dir} to sys.path")
    else:
        log("INFO", f"Root dir {root_dir} already in sys.path")

    return root_dir


def alias_deepseek_to_llm_env() -> None:
    """Kalau LLM_API_KEY kosong tapi DEEPSEEK_API_KEY ada, buat alias."""
    llm_key = os.getenv("LLM_API_KEY")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")

    if not llm_key and deepseek_key:
        os.environ["LLM_API_KEY"] = deepseek_key
        log("INFO", "LLM_API_KEY tidak ada, menggunakan DEEPSEEK_API_KEY.")
    elif llm_key:
        log("INFO", "LLM_API_KEY sudah ter-set secara eksplisit.")
    else:
        log("ERROR", "Tidak ada LLM_API_KEY maupun DEEPSEEK_API_KEY di env.")


def get_runtime_mode() -> str:
    """Tentukan mode runtime berdasarkan env."""
    explicit_mode = (os.getenv("BOT_MODE") or "").strip().lower()
    if explicit_mode in {"polling", "webhook"}:
        return explicit_mode

    return "webhook" if os.getenv("WEBHOOK_URL") else "polling"


def check_env() -> bool:
    """Cek env minimal yang dibutuhkan."""
    mode = get_runtime_mode()
    required = [
        "TELEGRAM_BOT_TOKEN",
        "SERIVA_ADMIN_ID",
        "DEEPSEEK_API_KEY",
    ]

    if mode == "webhook":
        required.append("WEBHOOK_URL")

    missing = [key for key in required if not os.getenv(key)]
    if missing:
        log("ERROR", f"Missing required env vars: {missing}")
        return False

    log("INFO", f"Runtime mode: {mode}")
    log("INFO", "All required env vars are set.")
    log("INFO", f"TELEGRAM_BOT_TOKEN: {os.getenv('TELEGRAM_BOT_TOKEN')[:10]}...")
    log("INFO", f"SERIVA_ADMIN_ID: {os.getenv('SERIVA_ADMIN_ID')}")
    if os.getenv("WEBHOOK_URL"):
        log("INFO", f"WEBHOOK_URL: {os.getenv('WEBHOOK_URL')}")
    if os.getenv("DEEPSEEK_API_KEY"):
        log("INFO", "DEEPSEEK_API_KEY is set (used as LLM_API_KEY if LLM_API_KEY was empty).")
    return True


# ==============================
# IMPORT CHECKS
# ==============================


def check_core_imports() -> bool:
    """Pastikan semua modul inti bisa di-import dengan root-level path."""
    mode = get_runtime_mode()
    modules_to_check = [
        "core.state_models",
        "core.emotion_engine",
        "core.scene_engine",
        "core.world_engine",
        "core.orchestrator",
        "roles.role_registry",
        "bot.webhook_main" if mode == "webhook" else "bot.main",
    ]

    all_ok = True
    log("INFO", "Checking core imports...")
    for mod_name in modules_to_check:
        try:
            importlib.import_module(mod_name)
            log("INFO", f"Import OK: {mod_name}")
        except Exception as exc:  # noqa: BLE001
            log("ERROR", f"Import failed: {mod_name} ({exc})")
            all_ok = False
    return all_ok


# ==============================
# MAIN ENTRYPOINT
# ==============================


def main() -> None:
    mode = get_runtime_mode()

    log("INFO", "============================================================")
    log("INFO", f"SERIVA Deployment Runner ({mode.capitalize()} Mode)")
    log("INFO", "============================================================")

    ensure_root_on_sys_path()
    alias_deepseek_to_llm_env()

    if not check_env():
        log("ERROR", "Environment check failed. Exiting.")
        sys.exit(1)

    if not check_core_imports():
        log(
            "ERROR",
            "Some core imports failed. Pastikan semua import sudah pakai root-level, "
            "contoh: 'from core.state_models import UserState' bukan "
            "'from seriva.core.state_models import UserState'.",
        )
        sys.exit(1)

    entry_module = "bot.webhook_main" if mode == "webhook" else "bot.main"

    try:
        bot_main = importlib.import_module(entry_module)
        log("INFO", f"Import OK: {entry_module}")
    except Exception as exc:  # noqa: BLE001
        log("ERROR", f"Gagal import {entry_module}: {exc}")
        sys.exit(1)

    log("INFO", f"Starting {entry_module}.main() ...")
    bot_main.main()


if __name__ == "__main__":
    main()
