"""Logging configuration using loguru.

Sets up rotating daily logs with separate info and error files.
"""

from __future__ import annotations

import sys

from loguru import logger

from app.config import Config, get_root_dir


def setup_logging(config: Config) -> None:
    """Configure loguru sinks based on project config.

    Removes default handler and adds:
    - stdout/stderr (INFO+)
    - rotating service log (INFO+)
    - rotating error log (ERROR+)

    Args:
        config: Project configuration with logging settings.
    """
    # Remove default handler
    logger.remove()

    stderr = sys.stderr
    if stderr is not None and callable(getattr(stderr, "write", None)):
        logger.add(
            stderr,
            level=config.logging.level,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "{message}"
            ),
        )

    # Ensure log directory exists
    root_dir = get_root_dir()
    log_dir = root_dir / config.logging.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    service_log = log_dir / "service.log"
    error_log = log_dir / "error.log"

    # Service log: INFO and above, rotating daily
    logger.add(
        str(service_log),
        level=config.logging.level,
        rotation=config.logging.rotation,
        retention=config.logging.retention,
        encoding="utf-8",
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "{name}:{function}:{line} | "
            "{message}"
        ),
    )

    # Error log: ERROR and above only
    logger.add(
        str(error_log),
        level="ERROR",
        rotation=config.logging.rotation,
        retention=config.logging.retention,
        encoding="utf-8",
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "{name}:{function}:{line} | "
            "{message}"
        ),
    )

    logger.info("Logging configured: level={}, rotation={}, retention={}",
                config.logging.level, config.logging.rotation, config.logging.retention)
