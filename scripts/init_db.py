#!/usr/bin/env python3
"""Initialize database schema. Safe to run multiple times (idempotent)."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tortoise import Tortoise

from src.app.core.config import settings


async def main() -> None:
    await Tortoise.init(
        db_url=settings.database_url,
        modules={"models": ["src.app.db.models"]},
    )
    await Tortoise.generate_schemas(safe=True)
    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
