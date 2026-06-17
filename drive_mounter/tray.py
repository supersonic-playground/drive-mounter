"""System tray indicator (AyatanaAppIndicator3)."""

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import Gtk, AyatanaAppIndicator3 as AppIndicator  # noqa: E402

from . import APP_ID, APP_NAME
from . import mounter


class TrayIndicator:
    def __init__(self, app):
        self.app = app
        self.indicator = AppIndicator.Indicator.new(
            APP_ID, "folder-remote",
            AppIndicator.IndicatorCategory.APPLICATION_STATUS)
        self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.indicator.set_title(APP_NAME)
        self.menu = Gtk.Menu()
        self.indicator.set_menu(self.menu)
        self.rebuild()

    def rebuild(self):
        for child in self.menu.get_children():
            self.menu.remove(child)

        header = Gtk.MenuItem(label=APP_NAME)
        header.set_sensitive(False)
        self.menu.append(header)
        self.menu.append(Gtk.SeparatorMenuItem())

        conns = self.app.store.connections
        if not conns:
            empty = Gtk.MenuItem(label="No connections")
            empty.set_sensitive(False)
            self.menu.append(empty)
        else:
            for conn in conns:
                mounted = mounter.is_mounted(conn.effective_mount_point())
                item = Gtk.CheckMenuItem(label=conn.name)
                item.set_active(mounted)
                item.connect("toggled", self._on_toggle, conn)
                self.menu.append(item)

        self.menu.append(Gtk.SeparatorMenuItem())

        unmount_all = Gtk.MenuItem(label="Disconnect all")
        unmount_all.connect("activate", lambda _i: self.app.disconnect_all())
        self.menu.append(unmount_all)

        manager = Gtk.MenuItem(label="Open Manager…")
        manager.connect("activate", lambda _i: self.app.show_window())
        self.menu.append(manager)

        self.menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", lambda _i: self.app.quit_app())
        self.menu.append(quit_item)

        self.menu.show_all()

    def _on_toggle(self, item, conn):
        # Reflect the user's intent; the actual state is re-synced on refresh.
        want = item.get_active()
        is_now = mounter.is_mounted(conn.effective_mount_point())
        if want and not is_now:
            self.app.toggle(conn)
        elif not want and is_now:
            self.app.toggle(conn)
