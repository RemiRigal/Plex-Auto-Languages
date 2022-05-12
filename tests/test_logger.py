import logging

from plex_auto_languages.utils.logger import init_logger, get_logger


def test_logger():
    logger = init_logger()
    assert isinstance(logger, logging.Logger)

    logger.debug("Test")
    logger.info("Test")
    logger.warning("Test")
    logger.error("Test")

    logger2 = get_logger()
    assert logger == logger2
