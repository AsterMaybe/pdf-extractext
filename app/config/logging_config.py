import logging
import os
import sys
import time


def setup_logging() -> None:
    """
    Configuración centralizada de logs para la app y el servidor.
    """

    tz = os.getenv('TZ', 'America/Argentina/Buenos_Aires')
    os.environ['TZ'] = tz

    if hasattr(time, 'tzset'):
        time.tzset()

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers = [console_handler]

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers = [console_handler]
        uvicorn_logger.propagate = False