"""
@service decorator and global dispatch table.

The decorator attaches ``human_fmt`` metadata and registers the function
in ``DISPATCH`` so CLI, REPL, and daemon can all find it by name.
"""
from __future__ import annotations

from typing import Callable

DISPATCH: dict[str, Callable] = {}


def service(
    *,
    human: Callable[[dict], str] | None = None,
    name: str | None = None,
    needs_session: bool = True,
):
    """Mark a function as a service and register it.

    Parameters
    ----------
    human:
        A callable ``(result_dict) -> str`` for human-friendly output.
    name:
        Override the dispatch key.  Defaults to the function name with
        a leading ``do_`` stripped (``do_click`` → ``"click"``).
    needs_session:
        Whether this service requires a ``ServiceContext`` as first arg.
        Set to ``False`` for global services like ``device_list`` or
        ``resource_status`` that don't operate on a connected session.
    """

    def decorator(fn: Callable) -> Callable:
        fn.human_fmt = human  # type: ignore[attr-defined]
        fn.needs_session = needs_session  # type: ignore[attr-defined]
        key = name or fn.__name__.removeprefix("do_")
        fn.dispatch_key = key  # type: ignore[attr-defined]
        DISPATCH[key] = fn
        return fn

    return decorator
