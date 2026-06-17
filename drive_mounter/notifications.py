"""Desktop notifications via libnotify."""

import gi

gi.require_version("Notify", "0.7")
from gi.repository import Notify  # noqa: E402

from . import APP_NAME  # noqa: E402

_initialized = False


def init():
    global _initialized
    if not _initialized:
        Notify.init(APP_NAME)
        _initialized = True


def notify(title, body="", icon="folder-remote", error=False):
    init()
    n = Notify.Notification.new(title, body, "dialog-error" if error else icon)
    if error:
        n.set_urgency(Notify.Urgency.CRITICAL)
    try:
        n.show()
    except Exception:
        pass  # notifications are best-effort; never crash the app over one
