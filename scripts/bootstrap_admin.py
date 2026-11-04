"""Create an initial organization admin locally, without a default public password."""

import argparse
import json
import secrets

from app.workspace.auth import CreateUser, hasher
from app.workspace.db import Organization, User, audit, data_dir, database
from sqlalchemy import select

parser = argparse.ArgumentParser()
parser.add_argument("--organization", default="lkpi")
parser.add_argument("--name", default="PT Likuid Pharmalab Indonesia")
parser.add_argument("--email", default="admin@baylab.local")
args = parser.parse_args()
password = secrets.token_urlsafe(20)
validated = CreateUser(
    organization=args.organization,
    email=args.email,
    name="Admin BAYLab",
    role="admin",
    password=password,
)
with database() as db:
    org = db.get(Organization, args.organization)
    if org and db.scalar(
        select(User).where(User.org_id == org.id, User.role == "admin")
    ):
        raise SystemExit(
            "Admin sudah ada; tidak mengubah kata sandi atau menimpa kredensial."
        )
    if not org:
        db.add(Organization(id=args.organization, name=args.name))
        db.flush()
    user = User(
        org_id=args.organization,
        email=args.email.lower(),
        name=validated.name,
        role="admin",
        password_hash=hasher.hash(password),
    )
    db.add(user)
    db.flush()
    audit(db, org.id if org else args.organization, user.id, "bootstrap_admin")
    target = data_dir() / ("initial-admin-" + args.organization + ".json")
    # Exclusive creation: do not overwrite an existing credential file.
    with target.open("x", encoding="utf-8") as stream:
        json.dump(
            {
                "organization": args.organization,
                "email": args.email,
                "password": password,
            },
            stream,
            indent=2,
        )
print("Admin dibuat. Kredensial disimpan di file privat: " + str(target.resolve()))
