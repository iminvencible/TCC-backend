from app.database import SessionLocal
from app.inmet_sync import InmetError, sync_inmet_warnings


def main() -> None:
    with SessionLocal() as db:
        try:
            imported, skipped = sync_inmet_warnings(db, actor=None)
        except InmetError as error:
            raise SystemExit(str(error)) from error
    print(f"INMET sincronizado: {imported} importados, {skipped} ignorados")


if __name__ == "__main__":
    main()
