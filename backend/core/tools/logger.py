import logging
import os

os.makedirs("./data/logs", exist_ok=True)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console = logging.StreamHandler()
        console.setFormatter(fmt)
        logger.addHandler(console)

        fh = logging.FileHandler("./data/logs/eye_of_god.log")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger
