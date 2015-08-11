import logging

logger = logging.getLogger(__name__)


def print_debug(msg):
    logger.debug(msg)


def print_warning(msg):
    logger.warning(msg)


def print_error(msg):
    logger.error(msg)


def print_critical(msg):
    logger.critical(msg)


def get_debug_printer(enabled=True):
    return _Printer(enabled, logger.debug)


def get_info_printer(enabled=True):
    return _Printer(enabled, logger.info)


def get_warning_printer(enabled=True):
    return _Printer(enabled, logger.warning)


def get_error_printer(enabled=True):
    return _Printer(enabled, logger.error)


def get_critical_printer(enabled=True):
    return _Printer(enabled, logger.critical)


class _Printer(object):
    def __init__(self, enabled=True, printer_function=None):
        self.printer_function = printer_function if enabled else None

    def __call__(self, msg, *nargs):
        if self.printer_function:
            if nargs:
                msg = msg % nargs
            self.printer_function(msg)

    def __nonzero__(self):
        return bool(self.printer_function)

# Thanks to J.F. Sebastian (http://stackoverflow.com/users/4279/j-f-sebastian)
# on stack overflow for the original source of tee and teed_call.
# Original question:
#   http://stackoverflow.com/questions/4984428/python-subprocess-get-childrens-output-to-file-and-terminal
# by user515766 (http://stackoverflow.com/users/515766/user515766)

def tee(infile, *files):
    """Print `infile` to `files` in a separate thread."""
    from threading  import Thread

    def fanout(infile, *files):
        for line in iter(infile.readline, ''):
            for f in files:
                f.write(line)
        infile.close()
    t = Thread(target=fanout, args=(infile,)+files)
    t.daemon = True
    t.start()
    return t

def teed_call(cmd_args, **kwargs):
    import sys
    from subprocess import Popen, PIPE, STDOUT

    stdout, stderr = [kwargs.pop(s, None) for s in 'stdout', 'stderr']
    kwargs['stdout'] = PIPE if stdout is not None else None
    if stderr == STDOUT:
        kwargs['stderr'] = stderr
    else:
        kwargs['stderr'] = PIPE if stderr is not None else None
    p = Popen(cmd_args, **kwargs)
    threads = []
    if stdout is not None:
        threads.append(tee(p.stdout, stdout, sys.stdout))
    if stderr not in (None, STDOUT):
        threads.append(tee(p.stderr, stderr, sys.stderr))
    for t in threads:
        t.join() # wait for IO completion
    return p.wait()