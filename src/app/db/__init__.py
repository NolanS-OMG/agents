from src.app.core.config import settings

TORTOISE_ORM = {
    "connections": {"default": settings.database_url},
    "apps": {
        "models": {
            "models": ["src.app.db.models"],
            "default_connection": "default",
        }
    },
}
