"""Provision the first administrator without demo accounts or weather."""

from getpass import getpass
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.database import SessionLocal
from app.models import User
from app.schemas import RegisterRequest
from app.security import hash_password
from app.seed import ensure_roles


def create_admin(db: Session, payload: RegisterRequest) -> User:
    email = str(payload.email).lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise ValueError("Este e-mail já está cadastrado; nenhuma conta foi alterada.")
    roles = ensure_roles(db)
    user = User(
        public_code=f"ADM-{uuid4().hex[:12].upper()}",
        name=payload.name,
        email=email,
        password_hash=hash_password(payload.password),
        role_id=roles["ADMIN"].id,
    )
    db.add(user)
    db.flush()
    record_audit(db, actor=user, action="ADMIN_BOOTSTRAPPED", target_type="user", target_id=user.id)
    db.commit()
    return user


def main() -> None:
    name = input("Nome do administrador: ").strip()
    email = input("E-mail: ").strip()
    password = getpass("Senha (maiúscula, minúscula, número e símbolo): ")
    if password != getpass("Confirme a senha: "):
        raise SystemExit("As senhas não coincidem; nenhuma conta foi criada.")
    try:
        payload = RegisterRequest(name=name, email=email, password=password)
    except ValidationError:
        # Never print validation input: it includes the password.
        raise SystemExit("Nome, e-mail ou senha inválidos; nenhuma conta foi criada.") from None
    try:
        with SessionLocal() as db:
            create_admin(db, payload)
    except ValueError as error:
        raise SystemExit(str(error)) from None
    print("Administrador criado. Entre pelo acesso profissional do site.")


if __name__ == "__main__":
    main()
