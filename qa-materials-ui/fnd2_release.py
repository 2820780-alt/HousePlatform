"""Apply the FND-2 package to an explicitly selected HousePlatform database."""
import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from uuid import UUID

from pydantic_settings import BaseSettings
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
parser = argparse.ArgumentParser()
parser.add_argument("--database", required=True, choices=("buildplatform", "houseplatform_vertical_20261113_171244",
                                                          "houseplatform_fnd2_restore_20261114",
                                                          "houseplatform_fnd2_followup_20261115"))
parser.add_argument("--apply", action="store_true")
parser.add_argument("--backup-sha256")
parser.add_argument("--restore-verified", action="store_true")
parser.add_argument("--backup-file", default="backup/fnd2-20261114/buildplatform.dump",
                    choices=("backup/fnd2-20261114/buildplatform.dump",
                             "backup/fnd2-followup-20261115/buildplatform.dump"))
args = parser.parse_args()

if args.database == "buildplatform" and args.apply:
    backup = ROOT / args.backup_file
    if not args.restore_verified or not args.backup_sha256 or not backup.is_file():
        raise SystemExit("Production requires the FND-2 backup hash and verified restore")
    with backup.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != args.backup_sha256.lower():
        raise SystemExit("FND-2 backup hash mismatch")

original_init = BaseSettings.__init__
def no_env_file(self, *values, **kwargs):
    kwargs["_env_file"] = None
    original_init(self, *values, **kwargs)
BaseSettings.__init__ = no_env_file
for key in ("DATABASE_URL", "DATABASE_URL_SYNC"):
    if key in os.environ:
        os.environ[key] = make_url(os.environ[key]).set(database=args.database).render_as_string(hide_password=False)
for key in ("MODULE1_REF_RUNTIME_MODE", "MODULE1_REF45_MODE", "MODULE1_REF6_MODE"):
    os.environ[key] = "legacy"
os.environ["APP_DEBUG"] = "false"

from app.config import settings
from app.database import async_session_factory
from app.models.material import Material
from app.services.module1_fnd2_materials import MaterialCandidate, import_material_candidates
from app.services.module1_fnd2_works import WorkCandidate, import_work_candidates
from app.services.module1_material_normalizer import normalize_title
from app.services.module2_fnd2_material_links import link_material_choices, link_unresolved_roles
from app.services.module2_fnd2_work_links import link_work_choices


async def main():
    if make_url(settings.DATABASE_URL).database != args.database:
        raise RuntimeError("Unexpected database")
    source = json.loads((ROOT / "src/modules/module1/seeds/fnd2_candidates.json").read_text(encoding="utf-8"))
    candidates = [MaterialCandidate(*row) for row in source["materials"]]
    works = [WorkCandidate(*row) for row in source["works"]]
    async with async_session_factory() as db:
        materials_result = await import_material_candidates(db, candidates)
        ids = materials_result["material_ids"]
        for key, name, identifier in source["existing"]:
            material = await db.get(Material, UUID(identifier))
            if not material or normalize_title(material.canonical_name).casefold() != normalize_title(name).casefold():
                raise ValueError(f"Existing material identity changed: {key}")
            ids[key] = identifier
        work_result = await import_work_candidates(db, works)
        material_links = await link_material_choices(db, material_ids=ids)
        conditional_roles = await link_unresolved_roles(db, rows=source["unresolved"])
        work_links = await link_work_choices(db, work_codes=work_result["work_codes"],
                                             work_notes={work.key: work.note for work in works})
        if args.apply:
            await db.commit()
        else:
            await db.rollback()
        print(json.dumps({"database": args.database, "applied": args.apply,
            "materials": {k: materials_result[k] for k in ("created", "reused")},
            "works": {k: work_result[k] for k in ("created", "reused")},
            "material_links": material_links, "conditional_roles": conditional_roles,
            "work_links": work_links}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
