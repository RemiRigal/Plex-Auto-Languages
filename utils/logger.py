import logging


class CustomFormatter(object):

    grey = "\x1b[38;21m"
    blue = "\x1b[38;5;39m"
    yellow = "\x1b[38;5;226m"
    red = "\x1b[38;5;196m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    fmt = "%(asctime)s [%(levelname)s] %(message)s"

    FORMATS = {
        logging.DEBUG: grey + fmt + reset,
        logging.INFO: blue + fmt + reset,
        logging.WARNING: yellow + fmt + reset,
        logging.ERROR: red + fmt + reset,
        logging.CRITICAL: bold_red + fmt + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def init_logger():
    logger = logging.getLogger("Logger")
    logger.setLevel(logging.INFO)
    logger_stream_handler = logging.StreamHandler()
    logger_stream_handler.setFormatter(CustomFormatter())
    logger.addHandler(logger_stream_handler)
    return logger


def get_logger():
    return logging.getLogger("Logger")
