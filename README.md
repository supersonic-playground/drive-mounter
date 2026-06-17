# Drive Mounter

A simple GTK GUI for Linux that mounts **SFTP/SSH** drives so you can browse
remote systems like local folders.

## Features

- **GUI connection manager** — add / edit / delete saved connections, with a
  menu bar, toolbar, right-click context menu, status bar and keyboard shortcuts
  (Ctrl+N new, Ctrl+E edit, Ctrl+M connect, Ctrl+U disconnect, F5 refresh).
- **Tray icon** (AppIndicator) — connect / disconnect any drive from the menu.
- **Desktop notifications** on connect, disconnect and errors.
- **Password auth** — passwords stored securely in the system keyring (libsecret).
- **Key / certificate auth** — point at a private key (`IdentityFile`).
- **Auto-reconnect** and keep-alive options baked into every mount.
- Mounts appear under `~/Mounts/<name>` by default (configurable per connection).

## Requirements

All of these ship with most Ubuntu/Mint/Debian desktops except `sshfs`:

```bash
sudo apt install sshfs python3-gi gir1.2-gtk-3.0 \
    gir1.2-ayatanaappindicator3-0.1 gir1.2-notify-0.7 gir1.2-secret-1
```

## Install

```bash
./install.sh
```

This installs to `~/.local`, adds a `drive-mounter` launcher and a desktop
menu entry. No root is needed for the app itself (only for `apt` if packages
are missing).

## Run without installing

```bash
./drive-mounter
```

## How it works

- **Mounting** runs `sshfs user@host:/remote/path /local/mount -o …`.
  For password auth the password is fed via `-o password_stdin`; for key auth
  it uses `-o IdentityFile=…`.
- **Unmounting** runs `fusermount -u` (with a lazy-unmount fallback).
- **Host keys** use `StrictHostKeyChecking=accept-new` — new hosts are trusted
  on first connect and pinned in `~/.ssh/known_hosts` thereafter.
- **Passwords** never touch the config file; they live in the default keyring
  collection. The config (`~/.config/drive-mounter/connections.json`) holds only
  non-secret connection details.

## Notes

- Key files with a passphrase work best via an `ssh-agent` (so no prompt is
  needed at mount time). Passphrase-less keys also work.
- Closing the window hides the app to the tray; use **Quit** in the tray menu
  to exit. Active mounts stay mounted after quitting.
