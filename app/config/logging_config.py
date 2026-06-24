import logging
import os
import time


def setup_logging() -> None:
    """
    Configuración de logs para la app.
    """

    os.environ['TZ'] = 'America/Argentina/Buenos_Aires'

    if hasattr(time, 'tzset'):
        time.tzset()

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()

    logging.basicConfig(
        level=getattr(logging, level_name, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )