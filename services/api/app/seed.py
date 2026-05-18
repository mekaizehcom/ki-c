"""Idempotent bootstrap: roles, default workspace, superadmin user.

TOTP is enrolled on the superadmin's first login (the auth flow returns an
enrollment URI / QR), so no secret is created here.
"""

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Role, User, Workspace
from app.security import hash_password

ROLES = [
    ("superadmin", "Full system access", 50),
    ("admin", "Manage workspaces, agents, tools, users", 40),
    ("developer", "Development agents and technical tools", 30),
    ("user", "Normal chat, search, documents", 20),
    ("restricted", "Restricted access to defined agents", 10),
]


def run() -> None:
    db = SessionLocal()
    try:
        for name, desc, rank in ROLES:
            if not db.get(Role, name):
                db.add(Role(name=name, description=desc, rank=rank))
        db.commit()

        slug = settings.default_workspace
        if not db.scalar(select(Workspace).where(Workspace.slug == slug)):
            db.add(Workspace(slug=slug, name="Company Default"))
            db.commit()

        uname = settings.bootstrap_admin_username
        if not db.scalar(select(User).where(User.username == uname)):
            db.add(
                User(
                    username=uname,
                    display_name=settings.bootstrap_admin_display_name,
                    password_hash=hash_password(settings.bootstrap_admin_password),
                    role="superadmin",
                    status="active",
                    allowed_channels=["web", "swisschat"],
                )
            )
            db.commit()
            print(f"[seed] created superadmin '{uname}' "
                  f"(TOTP enrolled on first login)")
        else:
            print(f"[seed] superadmin '{uname}' already exists")
    finally:
        db.close()


if __name__ == "__main__":
    run()
