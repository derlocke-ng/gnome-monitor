#!/usr/bin/env bash
# installer for gnome-monitor — kiwi convention: ./install.sh install|update|uninstall [--purge]
#
# User scope ONLY: it talks to the user's own GNOME session.
#
#   <prefix>/bin/gnome-monitor, gnome-monitor-panel
#   <prefix>/share/gnome-monitor/gnomemonitor.py   the core, shared by both
#   ~/.config/autostart/<app-id>-restore.desktop   re-applies the last layout at login
#   ~/.config/gnome-monitor/                        profiles + last-seen — kept unless --purge
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACTION="${1:-install}"

[[ "${KIWI_SCOPE:-user}" == "user" ]] || {
    echo "error: gnome-monitor is user-only (SCOPES=user)" >&2; exit 1; }

APP_ID=eu.kiwinetwork.GnomeMonitor
PREFIX="${KIWI_PREFIX:-$HOME/.local}"
BIN="$PREFIX/bin"
LIB="$PREFIX/share/gnome-monitor"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APPS="$DATA_HOME/applications"
ICON_DIR="$DATA_HOME/icons/hicolor/scalable/apps"
CONF_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/gnome-monitor"
AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"

say() { printf ':: %s\n' "$*"; }

# kiwi exports KIWI_GUI=0/1; standalone installs fall back to checking for
# the GTK4 stack, the same test kiwi uses
want_gui() {
    [[ ${KIWI_GUI:-} == 0 ]] && return 1
    [[ -n ${KIWI_GUI:-} ]] && return 0
    [[ -e /usr/lib64/girepository-1.0/Gtk-4.0.typelib ||
       -e /usr/lib/girepository-1.0/Gtk-4.0.typelib ]]
}

refresh_desktop() {
    command -v gtk-update-icon-cache >/dev/null 2>&1 && \
        gtk-update-icon-cache -qtf "$DATA_HOME/icons/hicolor" 2>/dev/null || true
    command -v update-desktop-database >/dev/null 2>&1 && \
        update-desktop-database -q "$APPS" 2>/dev/null || true
}

do_install() {
    say "installing gnome-monitor to $BIN"
    install -Dm755 "$SRC/bin/gnome-monitor" "$BIN/gnome-monitor"
    install -Dm644 "$SRC/lib/gnomemonitor.py" "$LIB/gnomemonitor.py"
    rm -rf "$LIB/__pycache__"

    if want_gui; then
        say "installing gnome-monitor-panel + desktop entry + icon"
        install -Dm755 "$SRC/gui/gnome-monitor-panel" "$BIN/gnome-monitor-panel"
        mkdir -p "$APPS"
        sed "s|^Exec=.*|Exec=$BIN/gnome-monitor-panel|" "$SRC/data/gnome-monitor-panel.desktop" \
            > "$APPS/$APP_ID.desktop"
        install -Dm644 "$SRC/data/gnome-monitor.svg" "$ICON_DIR/$APP_ID.svg"
        refresh_desktop
    else
        say "no GTK4 stack (or KIWI_GUI=0) — skipping panel"
    fi

    # GNOME does not remember a quietly applied layout; this puts the last one
    # back at login. Turned off in the app's settings, it stays off.
    if grep -qs '^RESTORE_AT_LOGIN=0' "$CONF_DIR/gnome-monitor.conf"; then
        say "restore at login is off in the settings — not installing the autostart entry"
    else
        say "installing the login restore (autostart entry)"
        mkdir -p "$AUTOSTART_DIR"
        sed "s|^Exec=.*|Exec=$BIN/gnome-monitor restore --delay 3|" "$SRC/data/gnome-monitor-restore.desktop" \
            > "$AUTOSTART_DIR/$APP_ID-restore.desktop"
    fi

    mkdir -p "$CONF_DIR/profiles"
    say "done — try: gnome-monitor show  |  gnome-monitor save <name>  |  gnome-monitor-panel"
}

do_uninstall() {
    rm -f "$BIN/gnome-monitor" "$BIN/gnome-monitor-panel" \
          "$APPS/$APP_ID.desktop" "$ICON_DIR/$APP_ID.svg" \
          "$AUTOSTART_DIR/$APP_ID-restore.desktop"
    rm -rf "$LIB"
    refresh_desktop

    if [[ "${KIWI_PURGE:-0}" == 1 || "${1:-}" == --purge ]]; then
        say "purging $CONF_DIR (profiles)"
        rm -rf "${CONF_DIR:?}"
    else
        say "kept: $CONF_DIR (profiles) — remove with: $0 uninstall --purge"
    fi
}

case "$ACTION" in
    install|update) do_install ;;
    uninstall) shift || true; do_uninstall "${1:-}" ;;
    *) echo "usage: $0 install|update|uninstall [--purge]" >&2; exit 1 ;;
esac
