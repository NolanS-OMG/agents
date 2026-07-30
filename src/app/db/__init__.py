from src.app.core.config import settings


def get_tortoise_config() -> dict:
    return {
        "connections": {"default": settings.database_url},
        "apps": {
            "models": {
                "models": ["src.app.db.models"],
                "default_connection": "default",
            }
        },
    }


TORTOISE_ORM = get_tortoise_config()
