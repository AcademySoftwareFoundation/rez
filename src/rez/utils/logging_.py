from contextlib import contextmanager
import logging
import time

logger = logging.getLogger(__name__)


def print_debug(msg):
    logger.debug(msg)


def print_info(msg):
    logger.info(msg)


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


@contextmanager
def log_duration(printer, msg):
    t1 = time.time()
    yield None

    t2 = time.time()
    secs = t2 - t1
    printer(msg, str(secs))

# Thanks to J.F. Sebastian (http://stackoverflow.com/users/4279/j-f-sebastian)
# on stack overflow for the original source of tee and teed_call.
# Original question:
#   http://stackoverflow.com/questions/4984428/python-subprocess-get-childrens-output-to-file-and-terminal
# by user515766 (http://stackoverflow.com/users/515766/user515766)

def tee(infile, *files, **kwargs):
    """Print `infile` to `files` in a separate thread."""
    from threading  import Thread, Condition
    import os
    import time

    flush_time = kwargs.pop('flush_time', 3.0)
    if kwargs:
        raise ValueError("Unrecognized kwargs: %s" % list(kwargs))

    input_done = Condition()

    def fanout(infile, *files):
        # don't use file.read / readline, because those will block until
        # either a certain # of bytes are read, or a newline is reached, while
        # os.read will return what's currently available, up to the given max,
        # and will only block if there is NOTHING currently available to read
        #
        # This can make a difference if, ie, a prompt is printed, without a
        # newline, and the program is waiting for user input...
        while True:
            input = os.read(infile.fileno(), 8192)
            if input == '':
                break
            for f in files:
                f.write(input)
        infile.close()

        input_done.acquire()
        try:
            input_done.notify()
        finally:
            input_done.release()

    args = (infile,) + files

    t = Thread(target=fanout, args=args)
    t.daemon = True
    t.start()

    # also need to make sure we flush the outputs occasionally...
    # we use the condition object to make sure that, when the program exits,
    # we're not sitting around waiting for the flush_time before the program
    # can exit
    def flush(infile, *files):
        input_done.acquire()
        try:
            while not infile.closed:
                for f in files:
                    f.flush()
                input_done.wait(flush_time)
        finally:
            input_done.release()

        # do one last flush...
        for f in files:
            f.flush()

    t2 = Thread(target=flush, args=args)
    t2.daemon = True
    t2.start()

    return (t, t2)

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
        threads.extend(tee(p.stdout, stdout, sys.stdout))
    if stderr not in (None, STDOUT):
        threads.extend(tee(p.stderr, stderr, sys.stderr))
    for t in threads:
        t.join() # wait for IO completion
    return p.wait()

# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.