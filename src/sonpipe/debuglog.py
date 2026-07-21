"""Opt-in breadcrumb logging for diagnosing hard crashes.

CED's ``sonpy`` is a compiled C++ library.  On some files/channels it fails an
internal assertion and calls ``abort()`` (SIGABRT) instead of raising a Python
exception.  ``abort()`` cannot be caught with ``try``/``except`` -- it kills the
whole interpreter immediately -- so an ordinary traceback is never produced and
the host (e.g. MATLAB) may only see a truncated or empty result.

To find *where* such a crash happens, sonpipe can write a breadcrumb line
immediately before and after every call into ``sonpy``.  The lines are written
with an unbuffered ``os.write`` (and ``fsync``) so they survive an ``abort()``
that skips Python's normal buffer flush.  The **last line in the log** is then
the ``sonpy`` call -- with its exact arguments -- that triggered the crash.

Logging is off by default and is controlled by the ``SONPIPE_LOG`` environment
variable:

* unset / ``""`` / ``"0"`` / ``"false"``  -> disabled (zero overhead)
* ``"1"`` / ``"true"``                     -> log to the default path
                                              ``~/.local/var/log/sonpipe-<uid>.log``
* any other value                          -> treated as a log file path
                                              (``~`` is expanded)

From MATLAB you can turn it on for a session with::

    setenv('SONPIPE_LOG', '1');   % or a full path

and then re-run the command that crashes; the child process inherits the
variable.  Turn it back off with ``setenv('SONPIPE_LOG', '')``.
"""

import os
import time

_state = {"resolved": False, "path": None}


def _default_path():
    base = os.path.expanduser("~/.local/var/log")
    try:
        os.makedirs(base, exist_ok=True)
    except OSError:
        base = os.path.expanduser("~")
    if hasattr(os, "getuid"):
        who = os.getuid()
    else:  # pragma: no cover - Windows has no getuid
        who = os.getpid()
    return os.path.join(base, "sonpipe-{}.log".format(who))


def logfile_path():
    """Return the resolved log file path, or ``None`` when logging is disabled."""
    if _state["resolved"]:
        return _state["path"]
    val = os.environ.get("SONPIPE_LOG", "")
    low = val.strip().lower()
    if low in ("", "0", "false", "no", "off"):
        path = None
    elif low in ("1", "true", "yes", "on"):
        path = _default_path()
    else:
        path = os.path.expanduser(val)
    _state["path"] = path
    _state["resolved"] = True
    return path


def enabled():
    return logfile_path() is not None


def log(event, **fields):
    """Append one breadcrumb line, flushed to the OS so it survives an abort()."""
    path = logfile_path()
    if path is None:
        return
    parts = ["{:.6f}".format(time.time()), "pid={}".format(os.getpid()), event]
    for key, value in fields.items():
        parts.append("{}={}".format(key, value))
    line = (" ".join(parts) + "\n").encode("utf-8", "replace")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, line)
            try:
                os.fsync(fd)
            except OSError:  # pragma: no cover - fsync may be unsupported
                pass
        finally:
            os.close(fd)
    except OSError:
        # Logging must never break a read; silently give up if we cannot write.
        pass


def call(name, func, *args, **kwargs):
    """Invoke ``func(*args, **kwargs)``, logging a breadcrumb around the call.

    When logging is disabled this is a thin passthrough with no overhead beyond
    a single dict lookup, so it is safe to route every ``sonpy`` call through it.

    The ``->`` line is written (and flushed) *before* the call, so if the call
    aborts the process, that line is the last thing in the log and names exactly
    which ``sonpy`` operation -- and with which arguments -- crashed.
    """
    if not enabled():
        return func(*args, **kwargs)
    arglist = ",".join([repr(a) for a in args]
                       + ["{}={!r}".format(k, v) for k, v in kwargs.items()])
    log("-> " + name, args=arglist)
    result = func(*args, **kwargs)
    size = getattr(result, "size", None)
    if size is None:
        try:
            size = len(result)
        except TypeError:
            size = "n/a"
    log("<- " + name, size=size)
    return result
