"""Exception types for sonpipe."""


class SonpipeError(Exception):
    """Base class for all sonpipe errors.

    Raised for user-facing problems such as a missing ``sonpy`` install, a file
    that cannot be opened, or a request for a channel that is not present.  The
    CLI catches this exception and prints a clean message to stderr instead of a
    traceback.
    """
