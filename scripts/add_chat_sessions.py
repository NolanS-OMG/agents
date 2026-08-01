from tortoise import Tortoise, run_async


async def migrate() -> None:
    await Tortoise.init(
        db_url="postgres://agente:dev_password_123@localhost:5434/agente_ia",
        modules={"models": ["src.app.db.models"]},
    )
    await Tortoise.generate_schemas()
    print("✅ Tablas chat_sessions y chat_messages creadas")
    await Tortoise.close_connections()


if __name__ == "__main__":
    run_async(migrate())
