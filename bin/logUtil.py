import logging

def initLogging(verbosity=1):
    """This function creates and configures (and returns) a logging module logger object.
       You may optionally specify an integer verbosity level, 0-3 (higher == more verbose).
       The returned logger can be then used in the usual way."""

    logger = logging.getLogger('base')
    logger.handlers = []    
    logger.addHandler(logging.StreamHandler())
    adjustVerbosity(logger, verbosity)
    return logger

def adjustVerbosity(logger, verbosity):
    """This function wraps the logger.setLevel() method and also replaces the formatter of
       any present StreamHandlers"""

    for handler in [x for x in logger.handlers if isinstance(x, logging.StreamHandler)]:
        if verbosity == 1:
            handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
            logger.setLevel(logging.INFO)
        elif verbosity == 2:
            handler.setFormatter(logging.Formatter(
                '[%(levelname)s][%(relativeCreated)dms %(module)s line%(lineno)d] %(message)s'
                )
            )
            logger.setLevel(logging.DEBUG)
        elif verbosity == 3:
            handler.setFormatter(logging.Formatter(
                '[%(levelname)s][%(relativeCreated)dms %(module)s::' +
                '%(funcName)s() line%(lineno)d (%(process)s/%(threadName)s)] %(message)s'
                )
            )
            logger.setLevel(logging.DEBUG)
        else:
            handler.setFormatter(logging.Formatter('%(message)s'))
            logger.setLevel(logging.WARNING)
        
