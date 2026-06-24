import logging
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

def setup_logging() -> None:
    """
    Configura el sistema de logging centralizado de la aplicación.
    Fuerza la zona horaria a GMT-3 (Argentina) para todos los registros.
    """
    tz_argentina = ZoneInfo("America/Argentina/Buenos_Aires")

    def gmt3_converter(timestamp: float | None = None):
        if timestamp is None:
            timestamp = time.time()  # Respaldo de seguridad si no recibe timestamp
        return datetime.fromtimestamp(timestamp, tz=tz_argentina).timetuple()

    logging.Formatter.converter = gmt3_converter

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )