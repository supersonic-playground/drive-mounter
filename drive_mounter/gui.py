"""GTK main window and the add/edit connection dialog."""

import os

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib  # noqa: E402

from . import APP_NAME, __version__
from .connection import Connection
from . import mounter


class ConnectionDialog(Gtk.Dialog):
    """Form for adding or editing a single connection."""

    def __init__(self, parent, conn=None, get_password=None):
        is_new = conn is None
        title = "Add Connection" if is_new else "Edit Connection"
        super().__init__(title=title, transient_for=parent, modal=True)
        self.set_default_size(460, -1)
        self.conn = conn or Connection()
        self._get_password = get_password

        self.add_button("Cancel", Gtk.ResponseType.CANCEL)
        self.add_button("Save", Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)

        grid = Gtk.Grid(row_spacing=8, column_spacing=10, margin=16)
        self.get_content_area().add(grid)
        row = 0

        def add_row(label, widget):
            nonlocal row
            lbl = Gtk.Label(label=label, halign=Gtk.Align.END)
            grid.attach(lbl, 0, row, 1, 1)
            widget.set_hexpand(True)
            grid.attach(widget, 1, row, 2, 1)
            row += 1
            return widget

        self.e_name = add_row("Name", Gtk.Entry(text=self.conn.name))
        self.e_host = add_row("Host", Gtk.Entry(text=self.conn.host,
                                                placeholder_text="example.com"))
        self.e_port = Gtk.SpinButton.new_with_range(1, 65535, 1)
        self.e_port.set_value(self.conn.port or 22)
        add_row("Port", self.e_port)
        self.e_user = add_row("Username", Gtk.Entry(text=self.conn.username))
        self.e_remote = add_row("Remote path",
                                Gtk.Entry(text=self.conn.remote_path,
                                          placeholder_text="(leave blank for login directory)"))

        # Auth type selector
        self.combo_auth = Gtk.ComboBoxText()
        self.combo_auth.append("password", "Password")
        self.combo_auth.append("key", "Key / Certificate")
        self.combo_auth.set_active_id(self.conn.auth_type or "password")
        self.combo_auth.connect("changed", self._on_auth_changed)
        add_row("Authentication", self.combo_auth)

        # Password field
        self.e_pass = Gtk.Entry(visibility=False,
                                placeholder_text="stored in system keyring")
        self.e_pass.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        if get_password and not is_new:
            existing = get_password(self.conn.id)
            if existing:
                self.e_pass.set_text(existing)
        self.row_pass = add_row("Password", self.e_pass)

        # Key file chooser
        key_box = Gtk.Box(spacing=6)
        self.e_key = Gtk.Entry(text=self.conn.key_path, hexpand=True,
                               placeholder_text="~/.ssh/id_ed25519")
        btn_browse = Gtk.Button(label="Browse…")
        btn_browse.connect("clicked", self._on_browse_key)
        key_box.pack_start(self.e_key, True, True, 0)
        key_box.pack_start(btn_browse, False, False, 0)
        self.row_key = add_row("Key file", key_box)

        # Mount point
        mp_box = Gtk.Box(spacing=6)
        self.e_mount = Gtk.Entry(text=self.conn.mount_point, hexpand=True,
                                 placeholder_text=self.conn.default_mount_point())
        btn_mp = Gtk.Button(label="Browse…")
        btn_mp.connect("clicked", self._on_browse_mount)
        mp_box.pack_start(self.e_mount, True, True, 0)
        mp_box.pack_start(btn_mp, False, False, 0)
        add_row("Mount point", mp_box)

        self.e_extra = add_row("Extra options",
                               Gtk.Entry(text=self.conn.extra_options,
                                         placeholder_text="e.g. allow_other,uid=1000"))

        self.chk_automount = Gtk.CheckButton(label="Connect automatically on startup")
        self.chk_automount.set_active(self.conn.automount)
        grid.attach(self.chk_automount, 1, row, 2, 1)
        row += 1

        self.show_all()
        self._on_auth_changed(self.combo_auth)

    def _on_auth_changed(self, _combo):
        is_key = self.combo_auth.get_active_id() == "key"
        self.e_pass.set_sensitive(not is_key)
        self.e_key.get_parent().set_sensitive(is_key)

    def _on_browse_key(self, _btn):
        dlg = Gtk.FileChooserDialog(title="Select private key", transient_for=self,
                                    action=Gtk.FileChooserAction.OPEN)
        dlg.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Select", Gtk.ResponseType.OK)
        ssh_dir = os.path.expanduser("~/.ssh")
        if os.path.isdir(ssh_dir):
            dlg.set_current_folder(ssh_dir)
        if dlg.run() == Gtk.ResponseType.OK:
            self.e_key.set_text(dlg.get_filename())
        dlg.destroy()

    def _on_browse_mount(self, _btn):
        dlg = Gtk.FileChooserDialog(title="Select mount point", transient_for=self,
                                    action=Gtk.FileChooserAction.SELECT_FOLDER)
        dlg.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Select", Gtk.ResponseType.OK)
        if dlg.run() == Gtk.ResponseType.OK:
            self.e_mount.set_text(dlg.get_filename())
        dlg.destroy()

    def get_result(self):
        """Return (connection, password_or_None). Call only after a Save response."""
        c = self.conn
        c.name = self.e_name.get_text().strip() or "Connection"
        c.host = self.e_host.get_text().strip()
        c.port = int(self.e_port.get_value())
        c.username = self.e_user.get_text().strip()
        c.remote_path = self.e_remote.get_text().strip()
        c.mount_point = self.e_mount.get_text().strip()
        c.auth_type = self.combo_auth.get_active_id()
        c.key_path = self.e_key.get_text().strip()
        c.extra_options = self.e_extra.get_text().strip()
        c.automount = self.chk_automount.get_active()
        password = self.e_pass.get_text() if c.auth_type == "password" else None
        return c, password


class MainWindow(Gtk.ApplicationWindow):
    """The connection manager window — menu bar, toolbar, list and status bar."""

    def __init__(self, app):
        super().__init__(application=app, title=APP_NAME)
        self.app = app
        self.set_default_size(620, 460)
        self.set_icon_name("folder-remote")

        # Widgets whose sensitivity depends on the current selection/state.
        self._needs_selection = []   # any row selected
        self._needs_mounted = []     # selected row is mounted
        self._needs_unmounted = []   # selected row is not mounted

        self.accel = Gtk.AccelGroup()
        self.add_accel_group(self.accel)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(vbox)
        vbox.pack_start(self._build_menubar(), False, False, 0)
        vbox.pack_start(self._build_toolbar(), False, False, 0)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        vbox.pack_start(scroller, True, True, 0)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.set_placeholder(self._make_placeholder())
        self.listbox.connect("row-selected", lambda *_: self._update_sensitivity())
        self.listbox.connect("row-activated", lambda _lb, _r: self._toggle_selected())
        self.listbox.connect("button-press-event", self._on_list_click)
        scroller.add(self.listbox)

        self.statusbar = Gtk.Statusbar()
        vbox.pack_start(self.statusbar, False, False, 0)

        self.connect("delete-event", self._on_delete)
        self.refresh()

    # ----- menu / toolbar construction ----------------------------------
    def _menu_item(self, label, callback, accel=None, groups=()):
        item = Gtk.MenuItem(label=label)
        item.connect("activate", lambda _i: callback())
        if accel:
            key, mod = accel
            item.add_accelerator("activate", self.accel, key, mod, Gtk.AccelFlags.VISIBLE)
        for g in groups:
            g.append(item)
        return item

    def _build_menubar(self):
        bar = Gtk.MenuBar()

        # File
        file_menu = Gtk.Menu()
        file_item = Gtk.MenuItem(label="_File", use_underline=True)
        file_item.set_submenu(file_menu)
        file_menu.append(self._menu_item(
            "New Connection…", self.app.on_add,
            (Gdk.KEY_n, Gdk.ModifierType.CONTROL_MASK)))
        file_menu.append(Gtk.SeparatorMenuItem())
        file_menu.append(self._menu_item(
            "Close Window", self.hide,
            (Gdk.KEY_w, Gdk.ModifierType.CONTROL_MASK)))
        file_menu.append(self._menu_item(
            "Quit", self.app.quit_app,
            (Gdk.KEY_q, Gdk.ModifierType.CONTROL_MASK)))
        bar.append(file_item)

        # Connection
        conn_menu = Gtk.Menu()
        conn_item = Gtk.MenuItem(label="_Connection", use_underline=True)
        conn_item.set_submenu(conn_menu)
        conn_menu.append(self._menu_item(
            "Connect", self._connect_selected,
            (Gdk.KEY_m, Gdk.ModifierType.CONTROL_MASK),
            groups=(self._needs_unmounted,)))
        conn_menu.append(self._menu_item(
            "Disconnect", self._disconnect_selected,
            (Gdk.KEY_u, Gdk.ModifierType.CONTROL_MASK),
            groups=(self._needs_mounted,)))
        conn_menu.append(self._menu_item(
            "Open in File Manager", self._open_selected,
            groups=(self._needs_mounted,)))
        conn_menu.append(Gtk.SeparatorMenuItem())
        conn_menu.append(self._menu_item(
            "Edit…", self._edit_selected,
            (Gdk.KEY_e, Gdk.ModifierType.CONTROL_MASK),
            groups=(self._needs_selection,)))
        conn_menu.append(self._menu_item(
            "Delete", self._delete_selected,
            (Gdk.KEY_Delete, 0),
            groups=(self._needs_selection,)))
        conn_menu.append(Gtk.SeparatorMenuItem())
        conn_menu.append(self._menu_item("Disconnect All", self.app.disconnect_all))
        bar.append(conn_item)

        # View
        view_menu = Gtk.Menu()
        view_item = Gtk.MenuItem(label="_View", use_underline=True)
        view_item.set_submenu(view_menu)
        view_menu.append(self._menu_item(
            "Refresh", self.app.refresh_ui, (Gdk.KEY_F5, 0)))
        bar.append(view_item)

        # Help
        help_menu = Gtk.Menu()
        help_item = Gtk.MenuItem(label="_Help", use_underline=True)
        help_item.set_submenu(help_menu)
        help_menu.append(self._menu_item("About", lambda: self.app.show_about(self)))
        bar.append(help_item)

        return bar

    def _tool_button(self, icon, label, tooltip, callback, groups=()):
        btn = Gtk.ToolButton(icon_name=icon, label=label)
        btn.set_tooltip_text(tooltip)
        btn.connect("clicked", lambda _b: callback())
        for g in groups:
            g.append(btn)
        return btn

    def _build_toolbar(self):
        tb = Gtk.Toolbar()
        tb.set_style(Gtk.ToolbarStyle.BOTH_HORIZ)
        tb.insert(self._tool_button("list-add", "Add", "Add a new connection",
                                    self.app.on_add), -1)
        tb.insert(self._tool_button("document-edit", "Edit", "Edit connection",
                                    self._edit_selected,
                                    groups=(self._needs_selection,)), -1)
        tb.insert(self._tool_button("user-trash", "Delete", "Delete connection",
                                    self._delete_selected,
                                    groups=(self._needs_selection,)), -1)
        tb.insert(Gtk.SeparatorToolItem(), -1)
        tb.insert(self._tool_button("network-connect", "Connect", "Mount this drive",
                                    self._connect_selected,
                                    groups=(self._needs_unmounted,)), -1)
        tb.insert(self._tool_button("network-disconnect", "Disconnect",
                                    "Unmount this drive", self._disconnect_selected,
                                    groups=(self._needs_mounted,)), -1)
        tb.insert(self._tool_button("folder-open", "Open", "Open in file manager",
                                    self._open_selected,
                                    groups=(self._needs_mounted,)), -1)
        tb.insert(Gtk.SeparatorToolItem(), -1)
        tb.insert(self._tool_button("view-refresh", "Refresh", "Refresh status",
                                    self.app.refresh_ui), -1)
        return tb

    # ----- selection helpers --------------------------------------------
    def _selected(self):
        row = self.listbox.get_selected_row()
        return getattr(row, "_conn", None) if row else None

    def _connect_selected(self):
        c = self._selected()
        if c and not mounter.is_mounted(c.effective_mount_point()):
            self.app.toggle(c)

    def _disconnect_selected(self):
        c = self._selected()
        if c and mounter.is_mounted(c.effective_mount_point()):
            self.app.toggle(c)

    def _toggle_selected(self):
        c = self._selected()
        if c:
            self.app.toggle(c)

    def _edit_selected(self):
        c = self._selected()
        if c:
            self.app.on_edit(c)

    def _delete_selected(self):
        c = self._selected()
        if c:
            self.app.on_delete(c)

    def _open_selected(self):
        c = self._selected()
        if c:
            self.app.open_in_files(c)

    def _update_sensitivity(self):
        conn = self._selected()
        mounted = bool(conn) and mounter.is_mounted(conn.effective_mount_point())
        for w in self._needs_selection:
            w.set_sensitive(conn is not None)
        for w in self._needs_mounted:
            w.set_sensitive(mounted)
        for w in self._needs_unmounted:
            w.set_sensitive(conn is not None and not mounted)

    # ----- context menu --------------------------------------------------
    def _on_list_click(self, _widget, event):
        if event.button != Gdk.BUTTON_SECONDARY:
            return False
        row = self.listbox.get_row_at_y(int(event.y))
        if row is None:
            return False
        self.listbox.select_row(row)
        menu = Gtk.Menu()
        conn = self._selected()
        mounted = conn and mounter.is_mounted(conn.effective_mount_point())
        if mounted:
            menu.append(self._menu_item("Disconnect", self._disconnect_selected))
            menu.append(self._menu_item("Open in File Manager", self._open_selected))
        else:
            menu.append(self._menu_item("Connect", self._connect_selected))
        menu.append(Gtk.SeparatorMenuItem())
        menu.append(self._menu_item("Edit…", self._edit_selected))
        menu.append(self._menu_item("Delete", self._delete_selected))
        menu.show_all()
        menu.popup_at_pointer(event)
        return True

    # ----- list rendering -----------------------------------------------
    def _make_placeholder(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                      margin=40, valign=Gtk.Align.CENTER)
        img = Gtk.Image.new_from_icon_name("folder-remote", Gtk.IconSize.DIALOG)
        lbl = Gtk.Label(label="No connections yet.\nUse File ▸ New Connection to add one.",
                        justify=Gtk.Justification.CENTER)
        box.pack_start(img, False, False, 0)
        box.pack_start(lbl, False, False, 0)
        box.show_all()
        return box

    def _on_delete(self, _w, _e):
        # Closing the window hides to tray instead of quitting.
        self.hide()
        return True

    def refresh(self):
        prev_id = getattr(self._selected(), "id", None)
        for child in self.listbox.get_children():
            self.listbox.remove(child)
        reselect = None
        mounted_count = 0
        for conn in self.app.store.connections:
            row = self._make_row(conn)
            self.listbox.add(row)
            if mounter.is_mounted(conn.effective_mount_point()):
                mounted_count += 1
            if conn.id == prev_id:
                reselect = row
        self.listbox.show_all()
        if reselect is not None:
            self.listbox.select_row(reselect)
        self._update_sensitivity()
        self._update_status(len(self.app.store.connections), mounted_count)

    def _update_status(self, total, mounted):
        ctx = self.statusbar.get_context_id("status")
        self.statusbar.pop(ctx)
        if total == 0:
            msg = "No connections"
        else:
            msg = "%d connection%s · %d connected" % (
                total, "" if total == 1 else "s", mounted)
        self.statusbar.push(ctx, msg)

    def _make_row(self, conn):
        row = Gtk.ListBoxRow()
        row._conn = conn
        box = Gtk.Box(spacing=10, margin=10)
        row.add(box)

        mounted = mounter.is_mounted(conn.effective_mount_point())
        dot = Gtk.Image.new_from_icon_name(
            "emblem-default" if mounted else "media-record",
            Gtk.IconSize.BUTTON)
        dot.set_tooltip_text("Connected" if mounted else "Disconnected")
        box.pack_start(dot, False, False, 0)

        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        name = Gtk.Label(xalign=0)
        name.set_markup("<b>%s</b>" % GLib.markup_escape_text(conn.name))
        loc = "%s@%s:%s" % (conn.username, conn.host, conn.remote_path or "~")
        sub = Gtk.Label(label=loc, xalign=0)
        sub.get_style_context().add_class("dim-label")
        text.pack_start(name, False, False, 0)
        text.pack_start(sub, False, False, 0)
        box.pack_start(text, True, True, 0)

        state = Gtk.Label(label="Connected" if mounted else "Disconnected")
        state.get_style_context().add_class("dim-label")
        box.pack_start(state, False, False, 0)

        return row


def error_dialog(parent, title, message):
    dlg = Gtk.MessageDialog(transient_for=parent, modal=True,
                            message_type=Gtk.MessageType.ERROR,
                            buttons=Gtk.ButtonsType.OK, text=title)
    dlg.format_secondary_text(message)
    dlg.run()
    dlg.destroy()


def confirm_dialog(parent, title, message):
    dlg = Gtk.MessageDialog(transient_for=parent, modal=True,
                            message_type=Gtk.MessageType.QUESTION,
                            buttons=Gtk.ButtonsType.OK_CANCEL, text=title)
    dlg.format_secondary_text(message)
    resp = dlg.run()
    dlg.destroy()
    return resp == Gtk.ResponseType.OK
