#!/usr/bin/env bash
# Install Drive Mounter for the current user (no root needed for the app itself).
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/drive-mounter"
DESKTOP_DIR="$HOME/.local/share/applications"

echo "==> Checking runtime dependencies"
missing_apt=()
command -v sshfs   >/dev/null 2>&1 || missing_apt+=("sshfs")
python3 -c "import gi; gi.require_version('Gtk','3.0')"                      2>/dev/null || missing_apt+=("python3-gi gir1.2-gtk-3.0")
python3 -c "import gi; gi.require_version('AyatanaAppIndicator3','0.1')"     2>/dev/null || missing_apt+=("gir1.2-ayatanaappindicator3-0.1")
python3 -c "import gi; gi.require_version('Notify','0.7')"                   2>/dev/null || missing_apt+=("gir1.2-notify-0.7")
python3 -c "import gi; gi.require_version('Secret','1')"                     2>/dev/null || missing_apt+=("gir1.2-secret-1")

if [ ${#missing_apt[@]} -gt 0 ]; then
  echo "Missing system packages. Install them with:"
  echo "    sudo apt install ${missing_apt[*]}"
  echo
  read -r -p "Run that now with sudo? [y/N] " ans
  if [[ "$ans" =~ ^[Yy]$ ]]; then
    sudo apt install -y ${missing_apt[*]}
  else
    echo "Aborting — install the packages above and re-run." >&2
    exit 1
  fi
fi

echo "==> Installing application files to $APP_DIR"
mkdir -p "$APP_DIR" "$BIN_DIR" "$DESKTOP_DIR"
cp -r "$SRC/drive_mounter" "$APP_DIR/"
cp "$SRC/drive-mounter" "$APP_DIR/drive-mounter"
chmod +x "$APP_DIR/drive-mounter"

echo "==> Linking launcher into $BIN_DIR"
ln -sf "$APP_DIR/drive-mounter" "$BIN_DIR/drive-mounter"

echo "==> Installing desktop entry"
cp "$SRC/data/drive-mounter.desktop" "$DESKTOP_DIR/drive-mounter.desktop"
update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "NOTE: $BIN_DIR is not on your PATH — add it to use 'drive-mounter' from a terminal." ;;
esac

echo
echo "Done. Launch it from your menu (Drive Mounter) or run: drive-mounter"
