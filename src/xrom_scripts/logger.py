"""Logging estandarizado para consola."""

import logging
import sys


def setup_logger(name: str = "xrom", level: str = "INFO") -> logging.Logger:
    """Configura un logger con salida a consola."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level, logging.INFO))

    # Evitar duplicar handlers si se llama multiples veces
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, level, logging.INFO))
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


# Logger por defecto que se puede importar directamente
logger = setup_logger()
