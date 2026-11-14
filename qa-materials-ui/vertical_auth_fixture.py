"""Create a throwaway QA login using credentials received privately on stdin."""
import asyncio
import json
import sys

import vertical_qa_server  # asserts the isolated database and disables SQL echo
from app.core.security import hash_password
from app.database import async_session_factory
from app.models.enums import UserRole, UserStatus
from app.models.module_access import ModuleAccess
from app.models.user import User


async def main():
    data = json.load(sys.stdin)
    if not data["email"].endswith("@example.invalid") or len(data["password"]) < 20:
        raise ValueError("Only generated QA credentials are allowed")
    level = "VIEW" if data.get("view_only") else "ADMIN"
    async with async_session_factory() as db:
        user = User(email=data["email"], password_hash=hash_password(data["password"]),
                    role=UserRole.SUPPLIER if data.get("view_only") else UserRole.ADMIN, status=UserStatus.ACTIVE)
        db.add(user)
        await db.flush()
        for code in ("MODULE_01_MATERIAL_HUB", "MODULE_02_KNOWLEDGE_BASE",
                     "MODULE_05_ESTIMATE_ENGINE", "MODULE_07_DIGITAL_HOUSE"):
            db.add(ModuleAccess(user_id=user.id, module_code=code, canonical_module_code=code,
                                access_level=level, access_scope="GLOBAL", status="ACTIVE"))
        await db.commit()
    print("QA login created")


asyncio.run(main())
