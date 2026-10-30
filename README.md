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
- Changes apply **quietly** — no *Keep Changes?* dialog. GNOME only remembers
  a layout it asked about, so a small autostart entry (`gnome-monitor
  restore`) puts the last quiet layout back when you log in, unless GNOME
  saved a newer one of its own meanwhile. Prefer GNOME's dialog and its own
  memory (it also survives a monitor being re-plugged)? Turn on *Ask to Keep
  Changes* in the panel's menu or `gnome-monitor settings ask-to-keep on`;
  `--persistent` / `--temporary` override it per call.
- In the panel, **Edit** above the picture lets you drag the screens around
  like in GNOME Settings — they snap to each other — and *Apply* sends the
  arrangement to Mutter.

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
gnome-monitor settings             # ask-to-keep / restore-at-login
gnome-monitor-panel                # the GTK panel ("Gnome Monitor" in the app grid)
```

`--dry-run` on any change asks Mutter whether the layout is valid and
changes nothing.

In the panel: click a profile to apply it, the switch turns a screen off and
on, *Main* picks the main screen, the gear opens resolution / refresh rate /
scale, *Edit* above the picture arranges the screens by dragging.

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

`kiwi uninstall gnome-monitor` removes the programs and the autostart entry
but keeps `~/.config/gnome-monitor` (your profiles); `--purge` removes that
too.

## License

GPL-3.0-or-later — see [LICENSE](LICENSE).
