from src.app.core.config import settings

TORTOISE_ORM = {
    "connections": {"default": settings.database_url},
    "apps": {
        "models": {
            "models": ["src.app.db.models", "aerich.models"],
            "default_connection": "default",
        }
    },
}


def get_tortoise_config() -> dict:
    return TORTOISE_ORM
