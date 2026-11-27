"""Recover a locked-out account, on the farm PC itself.

    python -m app.reset_password <username>

Asks for the new password twice, switches the account back on and signs it out everywhere.
"""

import asyncio
import getpass
import sys

from sqlalchemy import func, select

from app.core.security import hash_password, password_problem
from app.database import async_session_factory
from app.models.user import User
from app.services.events import log_event


async def reset(username: str, password: str) -> bool:
    async with async_session_factory() as db:
        user = await db.scalar(
            select(User).where(func.lower(User.username) == username.strip().lower())
        )
        if not user:
            return False
        user.password_hash = hash_password(password)
        user.is_active = True
        user.token_version = (user.token_version or 0) + 1
        await log_event(db, "user.password_changed", "user", user.id, actor_type="system")
        await db.commit()
    return True


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m app.reset_password <username>")
        return 2
    password = getpass.getpass("New password: ")
    if password_problem(password):
        print("The password needs at least 8 characters and at most 72 bytes.")
        return 1
    if getpass.getpass("Repeat it: ") != password:
        print("The two passwords differ. Nothing was changed.")
        return 1
    if not asyncio.run(reset(sys.argv[1], password)):
        print("No user has that name.")
        return 1
    print("Done. Sign in with the new password.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
