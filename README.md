# gnome-monitor

Save and switch display layouts on GNOME — resolution, refresh rate (VRR
included), position, scale and main screen per monitor — and turn single
monitors **off and on** when another computer uses them. A CLI plus a
GTK4/libadwaita panel, for the Kiwi Network toolset, managed by
[kiwi-updater](https://github.com/derlocke-ng/kiwi-updater).

Two computers, three screens, one desk: this one normally runs the 4K in the
middle and the 1440p on the left; the other one takes the right 1440p. When
the other machine needs the 4K too, switch it off here, work, switch it back
on — it comes back where it was, at the mode it had, as the main screen if it
was one. Or save each arrangement once and apply it with one click.

## How it works

- Talks to **Mutter's `org.gnome.Mutter.DisplayConfig`** D-Bus API, the same
  one GNOME Settings and `gdctl` use. Wayland and X11, no root, no extension.
- A **profile** is one JSON file in `~/.config/gnome-monitor/profiles/`:
  every connected monitor with on/off, mode, position, scale, rotation and
  whether it is the main screen. Monitors are matched by what they *are*
  (EDID vendor, product, serial), so a screen moved to another port is still
  found.
- Mutter's rules are kept for you: exactly one main screen, no overlaps, no
  gaps. Switch the middle screen off and the outer two close ranks; switch it
  on and they move apart again. If a saved mode is gone (another cable, say)
  the nearest one is used and you are told.
- Changes are **kept across reboots** by default, which also makes GNOME show
  its usual *Keep Changes?* dialog — a safety net: a layout that leaves you
  with a black screen reverts after 20 s. `--temporary` (or the panel's menu)
  skips both.

## Usage

```bash
gnome-monitor show                 # what is connected, on, where, at what mode — with a map
gnome-monitor save desk            # the current layout as profile "desk"
gnome-monitor save solo-right
gnome-monitor list                 # profiles; * marks the one in use
gnome-monitor apply desk
gnome-monitor off rog              # a screen by connector, part of its name, number or "main"
gnome-monitor on rog
gnome-monitor only odyssey hp      # exactly these on, every other off
gnome-monitor main odyssey         # the main screen
gnome-monitor mode rog 2560x1440@165
gnome-monitor modes rog            # what it offers
gnome-monitor-panel                # the GTK panel: switches, main-screen radio, dropdowns, profiles
```

`--dry-run` on any change asks Mutter whether the layout is valid and
changes nothing; `--temporary` applies without remembering.

## Install

Via kiwi (preferred) — gnome-monitor is in the
[kiwi-catalog](https://github.com/derlocke-ng/kiwi-catalog):

```bash
kiwi catalog add https://github.com/derlocke-ng/kiwi-catalog.git
kiwi install gnome-monitor
```

Manually: `./install.sh` (user-level only — `~/.local`, no root, ever). On a
machine without GTK4 (or with `kiwi install --cli-only`) the panel is
skipped; the CLI needs only `python3` with PyGObject, which GNOME ships.

`kiwi uninstall gnome-monitor` removes the programs but keeps
`~/.config/gnome-monitor` (your profiles); `--purge` removes that too.

## License

GPL-3.0-or-later — see [LICENSE](LICENSE).
