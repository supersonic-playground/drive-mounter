"""Connection model and persistence."""

import json
import os
import re
import uuid
from dataclasses import dataclass, field, asdict


def _config_dir():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    path = os.path.join(base, "drive-mounter")
    os.makedirs(path, exist_ok=True)
    return path


CONFIG_FILE = os.path.join(_config_dir(), "connections.json")


def _slug(name):
    s = re.sub(r"[^A-Za-z0-9.-]+", "-", name.strip())
    return s.strip("-") or "mount"


@dataclass
class Connection:
    name: str = "New Connection"
    host: str = ""
    port: int = 22
    username: str = ""
    remote_path: str = ""          # remote dir to mount; empty = login dir
    mount_point: str = ""          # local dir; auto-derived if empty
    auth_type: str = "password"    # "password" | "key"
    key_path: str = ""             # path to private key for key auth
    extra_options: str = ""        # extra comma-separated sshfs -o options
    automount: bool = True         # mount automatically when the app starts
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def default_mount_point(self):
        base = os.environ.get("XDG_DATA_HOME")
        # Mount under ~/Mounts/<name> by default — visible and easy to reach.
        return os.path.join(os.path.expanduser("~/Mounts"), _slug(self.name))

    def effective_mount_point(self):
        return os.path.expanduser(self.mount_point) if self.mount_point else self.default_mount_point()

    @property
    def label(self):
        loc = f"{self.username}@{self.host}" if self.username else self.host
        return f"{self.name}  ({loc})"

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})


class ConnectionStore:
    """Loads/saves the list of connections to a JSON file."""

    def __init__(self, path=CONFIG_FILE):
        self.path = path
        self.connections = []
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.connections = [Connection.from_dict(d) for d in data.get("connections", [])]
        except FileNotFoundError:
            self.connections = []
        except (json.JSONDecodeError, OSError, TypeError):
            self.connections = []

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"connections": [c.to_dict() for c in self.connections]}, f, indent=2)
        os.replace(tmp, self.path)

    def add(self, conn):
        self.connections.append(conn)
        self.save()

    def update(self, conn):
        for i, c in enumerate(self.connections):
            if c.id == conn.id:
                self.connections[i] = conn
                break
        else:
            self.connections.append(conn)
        self.save()

    def remove(self, conn):
        self.connections = [c for c in self.connections if c.id != conn.id]
        self.save()

    def get(self, conn_id):
        return next((c for c in self.connections if c.id == conn_id), None)
