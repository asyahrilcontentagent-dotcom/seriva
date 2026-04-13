import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
TARGET = "sroles"


def scan_for_sroles() -> None:
    print(f"Scanning for '{TARGET}' under {ROOT_DIR}...\n")

    found_any = False

    for path in ROOT_DIR.rglob("*.py"):
        # Lewati file test.py sendiri kalau perlu
        if path.name == "test.py":
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:  # noqa: BLE001
            print(f"[SKIP] {path}: {e}")
            continue

        if TARGET in text:
            found_any = True
            print(f"=== FOUND in: {path.relative_to(ROOT_DIR)} ===")
            for i, line in enumerate(text.splitlines(), start=1):
                if TARGET in line:
                    print(f"{i:4d}: {line}")
            print()

    if not found_any:
        print(f"Tidak ditemukan '{TARGET}' di project.")


if __name__ == "__main__":
    scan_for_sroles()
