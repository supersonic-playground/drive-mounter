"""Mount/unmount logic — a thin wrapper over the sshfs (FUSE) command."""

import os
import shutil
import subprocess


class MountError(Exception):
    pass


def sshfs_available():
    return shutil.which("sshfs") is not None


def _fusermount():
    return shutil.which("fusermount3") or shutil.which("fusermount") or "fusermount"


def _unescape_mount_field(s):
    # /proc/mounts octal-escapes spaces, tabs, newlines and backslashes.
    for esc, ch in (("\\040", " "), ("\\011", "\t"), ("\\012", "\n"), ("\\134", "\\")):
        s = s.replace(esc, ch)
    return s


def is_mounted(mount_point):
    """True if mount_point is an active mount. Reads /proc/mounts (no stat — a
    stale FUSE mount must not block us)."""
    target = os.path.abspath(os.path.expanduser(mount_point))
    try:
        with open("/proc/mounts", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.split(" ")
                if len(parts) >= 2 and _unescape_mount_field(parts[1]) == target:
                    return True
    except OSError:
        pass
    return False


def build_command(conn):
    """Build the sshfs argument list for a connection."""
    mount_point = conn.effective_mount_point()
    target = "{user}@{host}:{path}".format(
        user=conn.username, host=conn.host, path=conn.remote_path or ""
    )
    opts = [
        "reconnect",
        "ServerAliveInterval=15",
        "ServerAliveCountMax=3",
        "follow_symlinks",
        "StrictHostKeyChecking=accept-new",
    ]
    if conn.auth_type == "key":
        if not conn.key_path:
            raise MountError("No key file selected for key authentication.")
        opts.append("IdentityFile=%s" % os.path.expanduser(conn.key_path))
        opts.append("IdentitiesOnly=yes")
    else:
        opts.append("password_stdin")

    if conn.extra_options.strip():
        opts.append(conn.extra_options.strip())

    return ["sshfs", target, mount_point, "-p", str(conn.port), "-o", ",".join(opts)]


def mount(conn, password=None):
    """Mount the connection. Raises MountError on failure.

    sshfs reads the password (when using password auth) from stdin, performs the
    handshake, then daemonizes — so the call returns once the mount is live."""
    if not sshfs_available():
        raise MountError("sshfs is not installed. Install it with: sudo apt install sshfs")

    mount_point = conn.effective_mount_point()
    if is_mounted(mount_point):
        return  # already mounted

    try:
        os.makedirs(mount_point, exist_ok=True)
    except OSError as e:
        raise MountError("Cannot create mount point %s: %s" % (mount_point, e))

    cmd = build_command(conn)
    stdin_data = None
    if conn.auth_type == "password":
        stdin_data = (password or "") + "\n"

    try:
        proc = subprocess.run(
            cmd,
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=45,
        )
    except subprocess.TimeoutExpired:
        raise MountError("Timed out connecting to %s." % conn.host)
    except FileNotFoundError:
        raise MountError("sshfs command not found.")

    if proc.returncode != 0 or not is_mounted(mount_point):
        msg = (proc.stderr or proc.stdout or "").strip()
        raise MountError(msg or "sshfs failed to mount (exit %d)." % proc.returncode)


def unmount(mount_point):
    """Unmount the given mount point. Raises MountError on failure."""
    mp = os.path.abspath(os.path.expanduser(mount_point))
    if not is_mounted(mp):
        return
    fm = _fusermount()
    proc = subprocess.run([fm, "-u", mp], capture_output=True, text=True)
    if proc.returncode == 0:
        return
    # Fall back to a lazy unmount (handles "device is busy").
    lazy = subprocess.run([fm, "-uz", mp], capture_output=True, text=True)
    if lazy.returncode != 0:
        raise MountError((proc.stderr or lazy.stderr or "Unmount failed.").strip())
