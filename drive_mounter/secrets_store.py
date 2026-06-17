"""Password storage backed by the system keyring (libsecret / Secret Service)."""

import gi

gi.require_version("Secret", "1")
from gi.repository import Secret  # noqa: E402

from . import APP_ID  # noqa: E402

_SCHEMA = Secret.Schema.new(
    APP_ID,
    Secret.SchemaFlags.NONE,
    {"connection_id": Secret.SchemaAttributeType.STRING},
)


def store_password(conn_id, label, password):
    """Store (or replace) the password for a connection in the default keyring."""
    Secret.password_store_sync(
        _SCHEMA,
        {"connection_id": conn_id},
        Secret.COLLECTION_DEFAULT,
        f"Drive Mounter: {label}",
        password,
        None,
    )


def lookup_password(conn_id):
    """Return the stored password, or None if not present."""
    return Secret.password_lookup_sync(_SCHEMA, {"connection_id": conn_id}, None)


def clear_password(conn_id):
    """Remove any stored password for a connection."""
    try:
        Secret.password_clear_sync(_SCHEMA, {"connection_id": conn_id}, None)
    except Exception:
        pass
