import argparse
import time

from app.config import get_settings
from app.database import SessionLocal
from app.inmet_sync import InmetError, sync_inmet_warnings


def sync_once() -> bool:
    with SessionLocal() as db:
        try:
            imported, skipped = sync_inmet_warnings(db, actor=None)
        except InmetError as error:
            db.rollback()
            print(f"INMET indisponível: {error}; mantendo os avisos armazenados", flush=True)
            return False
    print(f"INMET sincronizado: {imported} importados, {skipped} ignorados", flush=True)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Sincroniza os avisos oficiais do INMET")
    parser.add_argument("--loop", action="store_true", help="repete em intervalos configurados")
    args = parser.parse_args()
    settings = get_settings()
    if not settings.inmet_enabled:
        print("Integração INMET desabilitada; nenhum aviso será consultado", flush=True)
        if not args.loop:
            raise SystemExit(1)
        while True:
            time.sleep(settings.inmet_sync_interval_minutes * 60)
    if not args.loop:
        if not sync_once():
            raise SystemExit(1)
        return
    while True:
        sync_once()
        time.sleep(settings.inmet_sync_interval_minutes * 60)


if __name__ == "__main__":
    main()
