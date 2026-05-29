import logging
import os

def setup_logging() -> None:
    """
    Configuración básica de logs para la app.

    """
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()

    logging.basicConfig(
        level=getattr(logging, level_name, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )