"""Application controller — wires the store, window, tray and mount engine."""

import threading

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio, GLib  # noqa: E402

from . import APP_ID, APP_NAME, __version__
from .connection import ConnectionStore
from . import mounter, notifications, secrets_store
from .gui import MainWindow, ConnectionDialog, error_dialog, confirm_dialog
from .tray import TrayIndicator


class DriveMounterApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.store = None
        self.window = None
        self.tray = None
        self._busy = set()  # connection ids with an in-flight mount/unmount

    # ----- lifecycle -----------------------------------------------------
    def do_startup(self):
        Gtk.Application.do_startup(self)
        notifications.init()
        self.store = ConnectionStore()
        self.tray = TrayIndicator(self)
        # Keep the process alive after the window is closed (tray app).
        self.hold()
        # Re-sync mount state periodically (catches drops / external mounts).
        GLib.timeout_add_seconds(10, self._periodic_refresh)
        # Mount the flagged connections once the main loop is running.
        GLib.idle_add(self._automount)

    def do_activate(self):
        self.show_window()
        if not mounter.sshfs_available():
            self._warn_sshfs_missing()

    # ----- window --------------------------------------------------------
    def show_window(self):
        if self.window is None:
            self.window = MainWindow(self)
        self.window.show_all()
        self.window.present()

    def _automount(self):
        if not mounter.sshfs_available():
            return False  # nothing to mount; startup warning already shown
        for conn in self.store.connections:
            if conn.automount and not mounter.is_mounted(conn.effective_mount_point()):
                self._run_async(conn, self._do_mount)
        return False  # run once

    def _periodic_refresh(self):
        self.refresh_ui()
        return True  # keep the timer running

    def refresh_ui(self):
        if self.window is not None and self.window.get_visible():
            self.window.refresh()
        if self.tray is not None:
            self.tray.rebuild()

    # ----- CRUD ----------------------------------------------------------
    def on_add(self):
        dlg = ConnectionDialog(self.window, conn=None)
        if dlg.run() == Gtk.ResponseType.OK:
            conn, password = dlg.get_result()
            self.store.add(conn)
            if conn.auth_type == "password" and password:
                secrets_store.store_password(conn.id, conn.name, password)
            self.refresh_ui()
        dlg.destroy()

    def on_edit(self, conn):
        dlg = ConnectionDialog(self.window, conn=conn,
                               get_password=secrets_store.lookup_password)
        if dlg.run() == Gtk.ResponseType.OK:
            updated, password = dlg.get_result()
            self.store.update(updated)
            if updated.auth_type == "password":
                if password:
                    secrets_store.store_password(updated.id, updated.name, password)
            else:
                secrets_store.clear_password(updated.id)
            self.refresh_ui()
        dlg.destroy()

    def on_delete(self, conn):
        if mounter.is_mounted(conn.effective_mount_point()):
            error_dialog(self.window, "Connection is mounted",
                         "Disconnect “%s” before deleting it." % conn.name)
            return
        if not confirm_dialog(self.window, "Delete connection?",
                              "Remove “%s”? This cannot be undone." % conn.name):
            return
        secrets_store.clear_password(conn.id)
        self.store.remove(conn)
        self.refresh_ui()

    # ----- mount / unmount ----------------------------------------------
    def toggle(self, conn):
        if conn.id in self._busy:
            return
        if mounter.is_mounted(conn.effective_mount_point()):
            self._run_async(conn, self._do_unmount)
        else:
            self._run_async(conn, self._do_mount)

    def disconnect_all(self):
        for conn in self.store.connections:
            if mounter.is_mounted(conn.effective_mount_point()):
                self._run_async(conn, self._do_unmount)

    def _run_async(self, conn, worker):
        self._busy.add(conn.id)
        threading.Thread(target=worker, args=(conn,), daemon=True).start()

    def _do_mount(self, conn):
        password = None
        if conn.auth_type == "password":
            password = secrets_store.lookup_password(conn.id)
            if not password:
                # Ask on the main thread, then resume.
                ev = threading.Event()
                holder = {}
                GLib.idle_add(self._prompt_password, conn, holder, ev)
                ev.wait()
                password = holder.get("password")
                if password is None:
                    self._finish(conn, None)
                    return
                if holder.get("save") and password:
                    secrets_store.store_password(conn.id, conn.name, password)
        try:
            mounter.mount(conn, password=password)
            self._finish(conn, None, action="Connected", body=conn.effective_mount_point())
        except mounter.MountError as e:
            self._finish(conn, str(e), action="Connection failed")

    def _do_unmount(self, conn):
        try:
            mounter.unmount(conn.effective_mount_point())
            self._finish(conn, None, action="Disconnected", body=conn.name)
        except mounter.MountError as e:
            self._finish(conn, str(e), action="Disconnect failed")

    def _finish(self, conn, error, action=None, body=""):
        def done():
            self._busy.discard(conn.id)
            if error:
                notifications.notify("%s — %s" % (action or "Error", conn.name),
                                     error, error=True)
                if self.window is not None and self.window.get_visible():
                    error_dialog(self.window, "%s: %s" % (action or "Error", conn.name),
                                 error)
            elif action:
                notifications.notify("%s: %s" % (action, conn.name), body)
            self.refresh_ui()
            return False
        GLib.idle_add(done)

    def _prompt_password(self, conn, holder, ev):
        dlg = Gtk.Dialog(title="Password for %s" % conn.name,
                         transient_for=self.window, modal=True)
        dlg.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dlg.add_button("Connect", Gtk.ResponseType.OK)
        dlg.set_default_response(Gtk.ResponseType.OK)
        box = dlg.get_content_area()
        box.set_spacing(8)
        box.set_border_width(14)
        box.add(Gtk.Label(label="Enter password for %s@%s:" % (conn.username, conn.host),
                          xalign=0))
        entry = Gtk.Entry(visibility=False, activates_default=True)
        entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        box.add(entry)
        save_chk = Gtk.CheckButton(label="Save in keyring")
        save_chk.set_active(True)
        box.add(save_chk)
        dlg.show_all()
        resp = dlg.run()
        if resp == Gtk.ResponseType.OK:
            holder["password"] = entry.get_text()
            holder["save"] = save_chk.get_active()
        else:
            holder["password"] = None
        dlg.destroy()
        ev.set()
        return False

    # ----- helpers -------------------------------------------------------
    def open_in_files(self, conn):
        path = conn.effective_mount_point()
        try:
            Gio.AppInfo.launch_default_for_uri(GLib.filename_to_uri(path, None), None)
        except Exception as e:
            error_dialog(self.window, "Could not open folder", str(e))

    def _warn_sshfs_missing(self):
        error_dialog(
            self.window, "sshfs is not installed",
            "Drive Mounter needs the 'sshfs' package to mount drives.\n\n"
            "Install it with:\n    sudo apt install sshfs\n\n"
            "Then restart Drive Mounter.")

    def show_about(self, parent=None):
        about = Gtk.AboutDialog(transient_for=parent or self.window, modal=True)
        about.set_program_name(APP_NAME)
        about.set_version(__version__)
        about.set_comments("Mount SFTP/SSH drives easily, with a tray icon and "
                           "desktop notifications.")
        about.set_logo_icon_name("folder-remote")
        about.set_website("https://github.com/winfsp/sshfs-win")
        about.set_website_label("Powered by sshfs (FUSE)")
        about.set_copyright("© Supersonic Playground")
        about.set_license_type(Gtk.License.MIT_X11)
        about.run()
        about.destroy()

    def quit_app(self):
        self.release()
        self.quit()


def main():
    import sys
    app = DriveMounterApp()
    return app.run(sys.argv)
