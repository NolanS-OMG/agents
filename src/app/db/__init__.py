def get_tortoise_config() -> dict:
    from src.app.core.config import settings

    return {
        "connections": {"default": settings.database_url},
        "apps": {
            "models": {
                "models": ["src.app.db.models"],
                "default_connection": "default",
            }
        },
    }
