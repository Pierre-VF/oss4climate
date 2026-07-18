"""
Module for logging
"""

import logging


def log_info(msg: str):
    """
    Log an informational message

    :param msg: Message to log
    """
    logging.info(msg)


def log_warning(msg: str):
    """
    Log a warning message

    :param msg: Warning message to log
    """
    logging.warning(msg)
