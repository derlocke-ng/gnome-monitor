"""gnomemonitor — the gnome-monitor core, shared by the CLI and the GTK panel.

Talks to Mutter's org.gnome.Mutter.DisplayConfig D-Bus API (the same one
GNOME Settings and gdctl use), keeps a layout valid for Mutter (exactly one
main screen, no overlaps, no gaps, origin at 0,0), and reads/writes profile
files in ~/.config/gnome-monitor/profiles/<name>.json.

A monitor is identified by its EDID (vendor, product, serial), not by the
connector: the same screen on another port is still the same screen.
"""
import json
import os
import re
import time
from dataclasses import dataclass, field

from gi.repository import Gio, GLib

BUS_NAME = "org.gnome.Mutter.DisplayConfig"
OBJECT_PATH = "/org/gnome/Mutter/DisplayConfig"
INTERFACE = "org.gnome.Mutter.DisplayConfig"

# ApplyMonitorsConfig "method"
VERIFY, TEMPORARY, PERSISTENT = 0, 1, 2
# "layout-mode"
LOGICAL, PHYSICAL = 1, 2
TRANSFORMS = ["normal", "90", "180", "270",
              "flipped", "flipped-90", "flipped-180", "flipped-270"]

CONF_DIR = os.path.join(GLib.get_user_config_dir(), "gnome-monitor")
PROFILES_DIR = os.path.join(CONF_DIR, "profiles")
LAST_SEEN_FILE = os.path.join(CONF_DIR, "last-seen.json")
LAST_APPLIED_FILE = os.path.join(CONF_DIR, "last-applied.json")
CONF_FILE = os.path.join(CONF_DIR, "gnome-monitor.conf")
MONITORS_XML = os.path.join(GLib.get_user_config_dir(), "monitors.xml")
AUTOSTART_FILE = os.path.join(GLib.get_user_config_dir(), "autostart",
                              "eu.kiwinetwork.GnomeMonitor-restore.desktop")
# keep in sync with data/gnome-monitor-restore.desktop
AUTOSTART_DESKTOP = """[Desktop Entry]
Type=Application
Name=Gnome Monitor (restore layout)
Comment=Re-applies the last display layout at login
Exec={exe} restore --delay 3
NoDisplay=true
OnlyShowIn=GNOME;
"""

NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
MODE_RE = re.compile(r"^(\d+)x(\d+)(?:@([\d.]+))?(\+vrr)?$")


class MonitorError(Exception):
    """Anything we want to show the user as one line."""


def fmt_rate(rate):
    """143.99 -> '143.99', 119.998 -> '120', 60.0 -> '60'."""
    s = f"{rate:.2f}".rstrip("0").rstrip(".")
    return s


# ── data ──────────────────────────────────────────────────────────────────────

@dataclass
class Mode:
    id: str                 # "3840x2160@143.990+vrr" — what Mutter wants back
    width: int
    height: int
    rate: float
    vrr: bool
    preferred_scale: float
    scales: list
    is_current: bool = False
    is_preferred: bool = False

    @property
    def resolution(self):
        return f"{self.width}×{self.height}"

    @property
    def hz(self):
        return f"{fmt_rate(self.rate)} Hz" + (" VRR" if self.vrr else "")

    def __str__(self):
        return f"{self.resolution} @ {self.hz}"


@dataclass(eq=False)     # identity: the same screen is the same object
class Monitor:
    connector: str
    vendor: str
    product: str
    serial: str
    display_name: str
    builtin: bool
    modes: list
    color_mode: object = None
    rgb_range: object = None
    mode: object = None     # the mode to use when the monitor is on

    @property
    def key(self):
        return f"{self.vendor}/{self.product}/{self.serial}"

    @property
    def name(self):
        return self.product or self.display_name or self.connector

    @property
    def current_mode(self):
        return next((m for m in self.modes if m.is_current), None)

    @property
    def preferred_mode(self):
        return next((m for m in self.modes if m.is_preferred), None)

    def resolutions(self):
        seen, out = set(), []
        for m in self.modes:
            if (m.width, m.height) not in seen:
                seen.add((m.width, m.height))
                out.append((m.width, m.height))
        return sorted(out, key=lambda r: (r[0] * r[1], r[0]), reverse=True)

    def modes_for(self, width, height):
        return sorted((m for m in self.modes if (m.width, m.height) == (width, height)),
                      key=lambda m: (m.rate, m.vrr), reverse=True)

    def find_mode(self, width, height, rate=None, vrr=None):
        """Best available mode: exact rate, else the nearest at that
        resolution (same VRR flavour first), else None."""
        cands = [m for m in self.modes if (m.width, m.height) == (width, height)]
        if not cands:
            return None
        if vrr is None and (self.mode or self.current_mode):
            vrr = (self.mode or self.current_mode).vrr   # keep the VRR choice
        if vrr is not None:
            same = [m for m in cands if m.vrr == vrr]
            cands = same or cands
        if rate is None:
            return max(cands, key=lambda m: m.rate)
        return min(cands, key=lambda m: abs(m.rate - rate))

    def find_mode_id(self, mode_id):
        """A saved mode id, or the closest the monitor offers now."""
        if not mode_id:
            return None
        exact = next((m for m in self.modes if m.id == mode_id), None)
        if exact:
            return exact
        mt = MODE_RE.match(mode_id)
        if not mt:
            return None
        w, h, rate, vrr = mt.groups()
        return self.find_mode(int(w), int(h), float(rate) if rate else None, bool(vrr))

    def options(self):
        opts = {}
        if self.color_mode is not None:
            opts["color-mode"] = GLib.Variant("u", self.color_mode)
        if self.rgb_range is not None:
            opts["rgb-range"] = GLib.Variant("u", self.rgb_range)
        return opts


@dataclass(eq=False)
class Logical:
    """One screen area. More than one monitor in it = mirrored."""
    x: int
    y: int
    scale: float
    transform: int
    primary: bool
    monitors: list

    @property
    def label(self):
        return " + ".join(m.name for m in self.monitors)

    def size(self, layout_mode):
        mode = self.monitors[0].mode
        w, h = mode.width, mode.height
        if layout_mode == LOGICAL:
            w, h = round(w / self.scale), round(h / self.scale)
        if self.transform % 2 == 1:
            w, h = h, w
        return w, h

    def rect(self, layout_mode):
        w, h = self.size(layout_mode)
        return Rect(self.x, self.y, w, h)


@dataclass
class Rect:
    x: int
    y: int
    w: int
    h: int

    @property
    def right(self):
        return self.x + self.w

    @property
    def bottom(self):
        return self.y + self.h

    @property
    def cy(self):
        return self.y + self.h // 2

    def overlaps(self, o):
        return self.x < o.right and o.x < self.right and self.y < o.bottom and o.y < self.bottom

    def adjacent(self, o):
        # Mutter's rule: a shared edge with some overlap along it
        if (self.x == o.right or self.right == o.x) and not (self.bottom <= o.y or self.y >= o.bottom):
            return True
        if (self.y == o.bottom or self.bottom == o.y) and not (self.right <= o.x or self.x >= o.right):
            return True
        return False


@dataclass
class State:
    serial: int
    monitors: list
    logicals: list
    layout_mode: int
    supports_layout_mode: bool


# ── D-Bus ─────────────────────────────────────────────────────────────────────

def _proxy():
    return Gio.DBusProxy.new_for_bus_sync(
        Gio.BusType.SESSION, Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES, None,
        BUS_NAME, OBJECT_PATH, INTERFACE, None)


def clean_error(e):
    msg = str(getattr(e, "message", e))
    # "GDBus.Error:org.gtk.GDBus.UnmappedGError.Quark._g_io_error_quark.Code0: text"
    return msg.rsplit(": ", 1)[-1].strip() if "GDBus.Error" in msg else msg


def get_state():
    """The live configuration, as Mutter reports it."""
    try:
        v = _proxy().call_sync("GetCurrentState", None, Gio.DBusCallFlags.NO_AUTO_START, -1, None)
    except GLib.Error as e:
        raise MonitorError(f"cannot reach Mutter's display config: {clean_error(e)}") from e
    serial, mons, lms, props = v.unpack()

    monitors = []
    for (connector, vendor, product, mserial), modes, mp in mons:
        mlist = []
        for mid, w, h, rate, pscale, scales, p in modes:
            mlist.append(Mode(mid, w, h, rate, p.get("refresh-rate-mode") == "variable",
                              pscale, list(scales), bool(p.get("is-current")),
                              bool(p.get("is-preferred"))))
        monitors.append(Monitor(connector, vendor, product, mserial,
                                mp.get("display-name", ""), bool(mp.get("is-builtin")),
                                mlist, mp.get("color-mode"), mp.get("rgb-range")))
    by_conn = {m.connector: m for m in monitors}

    logicals = []
    for x, y, scale, transform, primary, specs, _p in lms:
        members = []
        for conn, *_ in specs:
            m = by_conn.get(conn)
            if m and m.current_mode:
                m.mode = m.current_mode
                members.append(m)
        if members:
            logicals.append(Logical(x, y, scale, transform, primary, members))

    return State(serial, monitors, logicals, props.get("layout-mode", LOGICAL),
                 bool(props.get("supports-changing-layout-mode", False)))


# ── layout ────────────────────────────────────────────────────────────────────

class Layout:
    """A would-be configuration: the live state plus the changes you make.
    Call normalize() before apply(); it keeps Mutter's rules."""

    def __init__(self, state, logicals=None):
        self.state = state
        self.layout_mode = state.layout_mode
        src = state.logicals if logicals is None else logicals
        self.logicals = [Logical(l.x, l.y, l.scale, l.transform, l.primary, list(l.monitors))
                         for l in src]

    # ── queries ────────────────────────────────────────────────────────────
    def logical_of(self, monitor):
        return next((l for l in self.logicals if monitor in l.monitors), None)

    def is_on(self, monitor):
        return self.logical_of(monitor) is not None

    def ordered_logicals(self):
        return sorted(self.logicals, key=lambda l: (l.x, l.y))

    def monitors(self):
        """Every connected monitor: the ones that are on, left to right, then
        the ones that are off."""
        on = [m for l in self.ordered_logicals() for m in l.monitors]
        off = sorted((m for m in self.state.monitors if m not in on), key=lambda m: m.connector)
        return on + off

    def primary(self):
        return next((l for l in self.logicals if l.primary), None)

    def find(self, query):
        """A monitor by connector, by a part of its name, by its number in
        monitors(), or 'main'."""
        q = query.strip().lower()
        mons = self.monitors()
        if q in ("main", "primary"):
            p = self.primary()
            if not p:
                raise MonitorError("no main screen is set")
            return p.monitors[0]
        if q.isdigit() and 1 <= int(q) <= len(mons):
            return mons[int(q) - 1]
        exact = [m for m in mons if m.connector.lower() == q]
        if len(exact) == 1:
            return exact[0]
        subs = [m for m in mons
                if q in f"{m.connector} {m.vendor} {m.product} {m.display_name}".lower()]
        if len(subs) == 1:
            return subs[0]
        if not subs:
            raise MonitorError(f"no monitor matches '{query}' — see: gnome-monitor show")
        raise MonitorError(f"'{query}' matches several monitors: "
                           + ", ".join(f"{m.connector} ({m.name})" for m in subs))

    # ── changes ────────────────────────────────────────────────────────────
    def off(self, monitor):
        l = self.logical_of(monitor)
        if not l:
            return []
        l.monitors.remove(monitor)
        if not l.monitors:
            self.logicals.remove(l)
        return [f"{monitor.name} off"]

    def on(self, monitor, mode=None):
        """Turn a monitor on where it last was, with the mode it last had."""
        if self.is_on(monitor):
            return []
        seen = load_last_seen().get(monitor.key, {})
        if mode is None:
            mode = (monitor.find_mode_id(seen.get("mode")) or monitor.current_mode
                    or monitor.preferred_mode or (monitor.modes[0] if monitor.modes else None))
        if mode is None:
            raise MonitorError(f"{monitor.name} offers no modes")
        monitor.mode = mode
        scale = seen.get("scale", mode.preferred_scale)
        if not any(abs(scale - s) < 1e-3 for s in mode.scales):
            scale = mode.preferred_scale
        transform = seen.get("transform", "normal")
        transform = TRANSFORMS.index(transform) if transform in TRANSFORMS else 0
        lg = Logical(0, 0, scale, transform, False, [monitor])

        # where it was, relative to a screen that is still on — so a layout
        # that shifted meanwhile does not put it on top of another screen
        pos = None
        neighbours = seen.get("neighbours", {})
        for other in sorted(self.logicals, key=lambda l: not l.primary):
            okey = other.monitors[0].key
            if okey in neighbours:
                ox, oy = neighbours[okey]
                pos = (other.x + seen["x"] - ox, other.y + seen["y"] - oy)
                break
        if pos is None and "x" in seen and not self.logicals:
            pos = (seen["x"], seen["y"])
        if pos is None:
            pos = self._right_of_everything(lg)
        lg.x, lg.y = pos
        self.logicals.append(lg)
        notes = [f"{monitor.name} on at {mode}"]
        if seen.get("primary"):
            for o in self.logicals:
                o.primary = o is lg
            notes.append(f"{monitor.name} is the main screen again")
        return notes

    def set_main(self, monitor):
        l = self.logical_of(monitor)
        if not l:
            raise MonitorError(f"{monitor.name} is off — turn it on first")
        for o in self.logicals:
            o.primary = o is l
        return [f"{monitor.name} is the main screen"]

    def set_mode(self, monitor, mode):
        if not self.is_on(monitor):
            return self.on(monitor, mode)
        monitor.mode = mode
        l = self.logical_of(monitor)
        if not any(abs(l.scale - s) < 1e-3 for s in mode.scales):
            l.scale = mode.preferred_scale
        return [f"{monitor.name}: {mode}"]

    def set_scale(self, monitor, scale):
        l = self.logical_of(monitor)
        if not l:
            raise MonitorError(f"{monitor.name} is off")
        l.scale = scale
        return [f"{monitor.name}: scale {scale:g}"]

    def _right_of_everything(self, lg):
        others = [l for l in self.logicals if l is not lg]
        if not others:
            return (0, 0)
        lm = self.layout_mode
        anchor = max(others, key=lambda l: l.rect(lm).right)
        r = anchor.rect(lm)
        return (r.right, r.cy - lg.size(lm)[1] // 2)

    def normalize(self):
        """Make the layout one Mutter accepts. Returns what had to change."""
        notes = []
        lm = self.layout_mode
        self.logicals = [l for l in self.logicals if l.monitors and l.monitors[0].mode]
        if not self.logicals:
            return notes

        prim = [l for l in self.logicals if l.primary]
        if not prim:
            best = max(self.logicals, key=lambda l: (l.rect(lm).w * l.rect(lm).h, -l.x))
            best.primary = True
            notes.append(f"{best.label} is now the main screen")
        for l in prim[1:]:
            l.primary = False

        # overlaps: keep the left-to-right order, move an offender to the far right
        placed = []
        for l in self.ordered_logicals():
            if any(l.rect(lm).overlaps(p.rect(lm)) for p in placed):
                anchor = max(placed, key=lambda p: p.rect(lm).right)
                r = anchor.rect(lm)
                l.x, l.y = r.right, r.cy - l.size(lm)[1] // 2
                notes.append(f"{l.label} moved right of {anchor.label} (it overlapped another screen)")
            placed.append(l)

        # gaps: every island but the first docks to the right edge of what is placed
        comps = self._components()
        comps.sort(key=lambda c: min(l.x for l in c))
        union = list(comps[0])
        for comp in comps[1:]:
            anchor = max(union, key=lambda l: l.rect(lm).right)
            ar = anchor.rect(lm)
            lead = min(comp, key=lambda l: l.x)
            lr = lead.rect(lm)
            dx = ar.right - lr.x
            dy = 0
            if lr.bottom <= ar.y or lr.y >= ar.bottom:
                dy = ar.cy - lr.cy
            for l in comp:
                l.x += dx
                l.y += dy
            union.extend(comp)
            notes.append(f"{lead.label} moved next to {anchor.label} (there was a gap)")

        min_x = min(l.x for l in self.logicals)
        min_y = min(l.y for l in self.logicals)
        for l in self.logicals:
            l.x -= min_x
            l.y -= min_y
        return notes

    def _components(self):
        lm = self.layout_mode
        rest = list(self.logicals)
        comps = []
        while rest:
            comp = [rest.pop(0)]
            i = 0
            while i < len(comp):
                r = comp[i].rect(lm)
                for o in list(rest):
                    if r.adjacent(o.rect(lm)):
                        rest.remove(o)
                        comp.append(o)
                i += 1
            comps.append(comp)
        return comps

    # ── apply ──────────────────────────────────────────────────────────────
    def _variant(self, method):
        lms = []
        for l in self.ordered_logicals():
            mons = [(m.connector, m.mode.id, m.options()) for m in l.monitors]
            lms.append((l.x, l.y, float(l.scale), l.transform, bool(l.primary), mons))
        props = {}
        if self.state.supports_layout_mode:
            props["layout-mode"] = GLib.Variant("u", self.layout_mode)
        return GLib.Variant("(uua(iiduba(ssa{sv}))a{sv})",
                            (self.state.serial, method, lms, props))

    def apply(self, method=None):
        """VERIFY only checks; TEMPORARY applies quietly, and 'restore' puts
        it back at the next login; PERSISTENT makes GNOME ask to keep the
        changes and remember them itself. None = what the user configured."""
        if method is None:
            method = default_method()
        if not self.logicals:
            raise MonitorError("refusing to turn every screen off")
        try:
            _proxy().call_sync("ApplyMonitorsConfig", self._variant(method),
                               Gio.DBusCallFlags.NO_AUTO_START, -1, None)
        except GLib.Error as e:
            raise MonitorError(clean_error(e)) from e
        # a persistent one is Mutter's to remember — if the user keeps it
        if method == TEMPORARY:
            save_last_applied(self)

    # ── profiles / comparison ──────────────────────────────────────────────
    def to_profile(self):
        mons = []
        for i, l in enumerate(self.ordered_logicals()):
            for m in l.monitors:
                e = {"connector": m.connector, "vendor": m.vendor, "product": m.product,
                     "serial": m.serial, "name": m.display_name, "enabled": True,
                     "mode": m.mode.id, "x": l.x, "y": l.y, "scale": l.scale,
                     "transform": TRANSFORMS[l.transform], "primary": l.primary}
                if len(l.monitors) > 1:
                    e["mirror"] = i
                if m.color_mode is not None:
                    e["color_mode"] = m.color_mode
                if m.rgb_range is not None:
                    e["rgb_range"] = m.rgb_range
                mons.append(e)
        on = {m for l in self.logicals for m in l.monitors}
        for m in self.state.monitors:
            if m not in on:
                mons.append({"connector": m.connector, "vendor": m.vendor, "product": m.product,
                             "serial": m.serial, "name": m.display_name, "enabled": False})
        return {"version": 1, "saved": time.strftime("%Y-%m-%d %H:%M"),
                "layout_mode": "physical" if self.layout_mode == PHYSICAL else "logical",
                "monitors": mons}

    def signature(self):
        """What makes two layouts the same, for 'is this profile active?'"""
        sig = []
        for l in self.ordered_logicals():
            for m in l.monitors:
                sig.append((m.key, m.mode.id, l.x, l.y, round(l.scale, 3), l.transform, l.primary))
        return tuple(sorted(sig))

    def same_as(self, other):
        return self.signature() == other.signature()

    def compact(self):
        """'HP X27q · Odyssey G70NC ★ · ROG PG279Q off'"""
        parts = [m.name + (" ★" if l.primary else "")
                 for l in self.ordered_logicals() for m in l.monitors]
        on = {m for l in self.logicals for m in l.monitors}
        parts += [f"{m.name} off" for m in self.state.monitors if m not in on]
        return " · ".join(parts)

    def summary(self):
        """One line: 'Odyssey G70NC 3840×2160 @ 144 Hz VRR (main) · HP X27q … · ROG PG279Q off'"""
        parts = []
        for l in self.ordered_logicals():
            for m in l.monitors:
                parts.append(f"{m.name} {m.mode}" + (" (main)" if l.primary else ""))
        on = {m for l in self.logicals for m in l.monitors}
        for m in self.state.monitors:
            if m not in on:
                parts.append(f"{m.name} off")
        return " · ".join(parts)


def layout_from_profile(profile, state):
    """A Layout for a saved profile on the monitors connected now.
    Returns (layout, notes): what could not be done exactly."""
    notes = []
    lay = Layout(state, logicals=[])
    lay.layout_mode = PHYSICAL if profile.get("layout_mode") == "physical" else LOGICAL
    free = list(state.monitors)
    groups = {}
    for e in profile.get("monitors", []):
        if not e.get("enabled", True):
            continue
        label = e.get("product") or e.get("name") or e.get("connector", "?")
        m = _match_monitor(e, free)
        if not m:
            notes.append(f"{label} is not connected — skipped")
            continue
        free.remove(m)
        mode = m.find_mode_id(e.get("mode")) or m.preferred_mode or m.modes[0]
        if mode.id != e.get("mode"):
            notes.append(f"{m.name}: {e.get('mode')} is not available, using {mode}")
        m.mode = mode
        scale = float(e.get("scale", mode.preferred_scale))
        if not any(abs(scale - s) < 1e-3 for s in mode.scales):
            notes.append(f"{m.name}: scale {scale:g} is not available, using {mode.preferred_scale:g}")
            scale = mode.preferred_scale
        t = e.get("transform", "normal")
        transform = TRANSFORMS.index(t) if t in TRANSFORMS else 0
        if "color_mode" in e:
            m.color_mode = e["color_mode"]
        if "rgb_range" in e:
            m.rgb_range = e["rgb_range"]
        g = e.get("mirror")
        if g is not None and g in groups:
            groups[g].monitors.append(m)
            continue
        lg = Logical(int(e.get("x", 0)), int(e.get("y", 0)), scale, transform,
                     bool(e.get("primary")), [m])
        if g is not None:
            groups[g] = lg
        lay.logicals.append(lg)
    for m in free:
        if lay.logicals:
            notes.append(f"{m.name} stays off (not in this profile)")
    notes += lay.normalize()
    return lay, notes


def _match_monitor(entry, candidates):
    spec = (entry.get("vendor"), entry.get("product"), entry.get("serial"))
    hits = [m for m in candidates if (m.vendor, m.product, m.serial) == spec]
    if not hits:   # some screens report another serial on another port
        hits = [m for m in candidates if (m.vendor, m.product) == spec[:2]]
    if len(hits) > 1:
        same_port = [m for m in hits if m.connector == entry.get("connector")]
        hits = same_port or hits
    return hits[0] if hits else None


# ── files ─────────────────────────────────────────────────────────────────────

def check_name(name):
    if not NAME_RE.match(name or ""):
        raise MonitorError("a profile name uses letters, digits, '.', '-' and '_' only")
    return name


def profile_path(name):
    return os.path.join(PROFILES_DIR, f"{check_name(name)}.json")


def list_profiles():
    try:
        names = sorted(f[:-5] for f in os.listdir(PROFILES_DIR) if f.endswith(".json"))
    except OSError:
        return []
    return names


def load_profile(name):
    try:
        with open(profile_path(name)) as fh:
            return json.load(fh)
    except FileNotFoundError:
        raise MonitorError(f"no profile '{name}' — see: gnome-monitor list") from None
    except ValueError as e:
        raise MonitorError(f"profile '{name}' is not valid JSON: {e}") from None


def save_profile(name, layout):
    os.makedirs(PROFILES_DIR, exist_ok=True)
    data = layout.to_profile()
    data["name"] = check_name(name)
    with open(profile_path(name), "w") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    return data


def delete_profile(name):
    try:
        os.remove(profile_path(name))
    except FileNotFoundError:
        raise MonitorError(f"no profile '{name}'") from None


def active_profiles(layout):
    """Names of the saved profiles that equal the given layout."""
    names = []
    for name in list_profiles():
        try:
            other, _ = layout_from_profile(load_profile(name), layout.state)
        except MonitorError:
            continue
        if other.logicals and other.same_as(layout):
            names.append(name)
    return names


def load_last_seen():
    try:
        with open(LAST_SEEN_FILE) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def remember(layout):
    """Note where every screen that is on sits right now, so 'on' can put
    it back there later. Writes only when something changed."""
    seen = load_last_seen()
    positions = {m.key: [l.x, l.y] for l in layout.logicals for m in l.monitors}
    changed = False
    for l in layout.logicals:
        for m in l.monitors:
            entry = {"connector": m.connector, "name": m.name, "mode": m.mode.id,
                     "scale": l.scale, "transform": TRANSFORMS[l.transform],
                     "x": l.x, "y": l.y, "primary": l.primary,
                     "neighbours": {k: v for k, v in positions.items() if k != m.key}}
            if seen.get(m.key) != entry:
                seen[m.key] = entry
                changed = True
    if changed:
        os.makedirs(CONF_DIR, exist_ok=True)
        tmp = LAST_SEEN_FILE + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(seen, fh, indent=2)
        os.replace(tmp, LAST_SEEN_FILE)


def save_last_applied(layout):
    data = layout.to_profile()
    data["applied"] = time.strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs(CONF_DIR, exist_ok=True)
    tmp = LAST_APPLIED_FILE + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, LAST_APPLIED_FILE)


def load_last_applied():
    try:
        with open(LAST_APPLIED_FILE) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def mutter_saved_later():
    """True when GNOME wrote its own monitors.xml after our last quiet apply —
    then it remembers a newer layout and 'restore' must not override it."""
    try:
        return os.path.getmtime(MONITORS_XML) > os.path.getmtime(LAST_APPLIED_FILE)
    except OSError:
        return False


def cli_path():
    here = os.path.dirname(os.path.realpath(__file__))
    for c in (os.path.join(here, "..", "..", "bin", "gnome-monitor"),   # <prefix>/share/gnome-monitor
              os.path.join(here, "..", "bin", "gnome-monitor")):        # the repo's lib/
        if os.path.exists(c):
            return os.path.normpath(c)
    return "gnome-monitor"


# ── settings ──────────────────────────────────────────────────────────────────

def ask_to_keep():
    """Apply persistently, so GNOME shows its 'Keep Changes?' dialog and
    remembers the layout itself. Off: apply quietly, restore at login."""
    return conf_get("PERSISTENT", "0") == "1"


def set_ask_to_keep(on):
    conf_set("PERSISTENT", "1" if on else "0")


def default_method():
    return PERSISTENT if ask_to_keep() else TEMPORARY


def restore_at_login():
    return conf_get("RESTORE_AT_LOGIN", "1") == "1"


def set_restore_at_login(on):
    conf_set("RESTORE_AT_LOGIN", "1" if on else "0")
    if on:
        os.makedirs(os.path.dirname(AUTOSTART_FILE), exist_ok=True)
        with open(AUTOSTART_FILE, "w") as fh:
            fh.write(AUTOSTART_DESKTOP.format(exe=cli_path()))
    else:
        try:
            os.remove(AUTOSTART_FILE)
        except FileNotFoundError:
            pass


def conf_get(key, default):
    try:
        with open(CONF_FILE) as fh:
            for line in fh:
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return default


def conf_set(key, value):
    os.makedirs(CONF_DIR, exist_ok=True)
    lines, found = [], False
    try:
        with open(CONF_FILE) as fh:
            lines = fh.readlines()
    except OSError:
        pass
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            found = True
    if not found:
        lines.append(f"{key}={value}\n")
    with open(CONF_FILE, "w") as fh:
        fh.writelines(lines)


# ── keyboard shortcuts ────────────────────────────────────────────────────────
# GNOME's own custom shortcuts (Settings → Keyboard), one per profile, each
# running `gnome-monitor apply <name>` — gnome-settings-daemon handles the key.

MEDIA_KEYS_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
CUSTOM_KEY_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
CUSTOM_KEY_DIR = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"
SHORTCUT_PREFIX = "gnome-monitor-"


def shortcuts_available():
    src = Gio.SettingsSchemaSource.get_default()
    return bool(src and src.lookup(MEDIA_KEYS_SCHEMA, True) and src.lookup(CUSTOM_KEY_SCHEMA, True))


def _media_keys():
    if not shortcuts_available():
        raise MonitorError("GNOME's custom shortcuts are not available here "
                           "(no gnome-settings-daemon schemas)")
    return Gio.Settings.new(MEDIA_KEYS_SCHEMA)


def _shortcut_path(name):
    return f"{CUSTOM_KEY_DIR}{SHORTCUT_PREFIX}{check_name(name)}/"


def parse_binding(text):
    """'super+shift+1' or '<Super><Shift>1' -> '<Super><Shift>1'."""
    t = text.strip()
    if "<" in t:
        return t
    parts = [p for p in re.split(r"[+\s]+", t) if p]
    if not parts:
        raise MonitorError("a shortcut looks like super+1, ctrl+alt+F2 or <Super><Shift>1")
    names = {"super": "Super", "win": "Super", "ctrl": "Control", "control": "Control",
             "alt": "Alt", "shift": "Shift", "meta": "Meta", "hyper": "Hyper"}
    bad = [p for p in parts[:-1] if p.lower() not in names]
    if bad:
        raise MonitorError(f"unknown modifier '{bad[0]}' — use super, ctrl, alt, shift")
    if len(parts) == 1 and not re.match(r"^F\d+$", parts[0], re.I):
        raise MonitorError("a plain key would get in the way of typing — add super, ctrl or alt")
    return "".join(f"<{names[p.lower()]}>" for p in parts[:-1]) + parts[-1]


def shortcut_get(name):
    """The accelerator bound to a profile ('<Super>1'), or None."""
    if not shortcuts_available():
        return None
    base = Gio.Settings.new(MEDIA_KEYS_SCHEMA)
    path = _shortcut_path(name)
    if path not in base.get_strv("custom-keybindings"):
        return None
    return Gio.Settings.new_with_path(CUSTOM_KEY_SCHEMA, path).get_string("binding") or None


def shortcut_set(name, binding):
    base = _media_keys()
    path = _shortcut_path(name)
    kb = Gio.Settings.new_with_path(CUSTOM_KEY_SCHEMA, path)
    kb.set_string("name", f"Gnome Monitor: {name}")
    kb.set_string("command", f"{cli_path()} apply {name}")
    kb.set_string("binding", binding)
    paths = base.get_strv("custom-keybindings")
    if path not in paths:
        base.set_strv("custom-keybindings", paths + [path])
    Gio.Settings.sync()


def shortcut_clear(name):
    if not shortcuts_available():
        return
    base = Gio.Settings.new(MEDIA_KEYS_SCHEMA)
    path = _shortcut_path(name)
    paths = base.get_strv("custom-keybindings")
    if path in paths:
        base.set_strv("custom-keybindings", [p for p in paths if p != path])
    kb = Gio.Settings.new_with_path(CUSTOM_KEY_SCHEMA, path)
    for key in ("name", "command", "binding"):
        kb.reset(key)
    Gio.Settings.sync()


def shortcuts_all():
    """{profile: binding} for every shortcut of ours."""
    if not shortcuts_available():
        return {}
    out = {}
    head = CUSTOM_KEY_DIR + SHORTCUT_PREFIX
    for path in Gio.Settings.new(MEDIA_KEYS_SCHEMA).get_strv("custom-keybindings"):
        if path.startswith(head):
            name = path[len(head):].rstrip("/")
            out[name] = Gio.Settings.new_with_path(CUSTOM_KEY_SCHEMA, path).get_string("binding")
    return out


# ── arranging ─────────────────────────────────────────────────────────────────
# A port of GNOME Settings' find_best_snapping() (panels/display/
# cc-display-arrangement.c), with its "infinite" major snap distance: the
# dragged screen always attaches to the nearest edge of another screen and
# slides along it; corners and centres click into line when within
# MINOR_SNAP_DISTANCE widget pixels; it never detaches (MIN_OVERLAP).

SNAP_X, SNAP_Y, SNAP_BOTH = 1, 2, 3
MINOR_SNAP_DISTANCE = 6     # widget px (GNOME: 5)
MIN_OVERLAP = 25            # logical px


def snap(layout, lg, x, y, scale):
    """Where the dragged screen `lg` lands for the pointer position (x, y)
    in layout coordinates; `scale` is layout px -> widget px."""
    lm = layout.layout_mode
    w, h = lg.size(lm)
    x1, y1, x2, y2 = x, y, x + w, y + h
    sd = {"snapped": 0, "x": x, "y": y, "dx": 0.0, "dy": 0.0}

    def dist(nx, ny):
        return abs(x - nx) * scale, abs(y - ny) * scale

    def maybe(nx, ny, snapped, major, minor_unlimited=0):
        dx, dy = dist(nx, ny)
        d = max(dx, dy)
        # the minor axis must be (nearly) in place — unless the candidate
        # only pulls the screen back from hanging over an edge
        if major == SNAP_X and dy > MINOR_SNAP_DISTANCE:
            if ny > y and minor_unlimited <= 0:
                return
            if ny < y and minor_unlimited >= 0:
                return
        if major == SNAP_Y and dx > MINOR_SNAP_DISTANCE:
            if nx > x and minor_unlimited <= 0:
                return
            if nx < x and minor_unlimited >= 0:
                return
        update = 0
        if snapped == SNAP_BOTH:
            if sd["snapped"] == 0:
                update = SNAP_BOTH
            if (major == SNAP_X and dx < sd["dx"]) or (major == SNAP_Y and dy < sd["dy"]):
                update = SNAP_BOTH
            if (sd["snapped"] == SNAP_X and d <= sd["dx"]) or (sd["snapped"] == SNAP_Y and d <= sd["dy"]):
                update = SNAP_BOTH
            if ((sd["snapped"] == SNAP_X and major == SNAP_X and nx == sd["x"])
                    or (sd["snapped"] == SNAP_Y and major == SNAP_Y and ny == sd["y"])):
                update = SNAP_BOTH
        elif snapped == SNAP_X:
            if dx < sd["dx"] or not (sd["snapped"] & SNAP_X):
                update = SNAP_X
        else:
            if dy < sd["dy"] or not (sd["snapped"] & SNAP_Y):
                update = SNAP_Y
        if update & SNAP_X:
            sd["dx"], sd["x"] = dx, nx
            sd["snapped"] |= SNAP_X
        if update & SNAP_Y:
            sd["dy"], sd["y"] = dy, ny
            sd["snapped"] |= SNAP_Y

    for o in layout.logicals:
        if o is lg:
            continue
        r = o.rect(lm)
        _x1, _y1, _x2, _y2, _w, _h = r.x, r.y, r.right, r.bottom, r.w, r.h
        top, bottom, left, right = _y1 - h, _y2, _x1 - w, _x2

        dy = 9999.0
        if x1 <= _x2 and _x1 <= x2:                 # overlap on the X axis
            dy = min(dist(x1, top)[1], dist(x1, bottom)[1])
        dx = 9999.0
        if y1 <= _y2 and _y1 <= y2:                 # overlap on the Y axis
            dx = min(dist(left, y1)[0], dist(right, y1)[0])
        # slide along the nearer edge of this screen
        if dy < dx:
            maybe(x1, top, SNAP_Y, SNAP_Y)
            maybe(x1, bottom, SNAP_Y, SNAP_Y)
        elif dx < 9999:
            maybe(left, y1, SNAP_X, SNAP_X)
            maybe(right, y1, SNAP_X, SNAP_X)
        # corners and centres in line, above and below
        for nx in (_x1, _x2 - w, _x1 + _w // 2 - w // 2):
            maybe(nx, top, SNAP_BOTH, SNAP_Y)
            maybe(nx, bottom, SNAP_BOTH, SNAP_Y)
        # corners in line, left and right
        for ny in (_y1, _y2 - h):
            maybe(left, ny, SNAP_BOTH, SNAP_X)
            maybe(right, ny, SNAP_BOTH, SNAP_X)
        # hanging over an edge: keep a minimal overlap, never detach
        maybe(_x1 - w + MIN_OVERLAP, top, SNAP_BOTH, SNAP_Y, 1)
        maybe(_x2 - MIN_OVERLAP, top, SNAP_BOTH, SNAP_Y, -1)
        maybe(_x1 - w + MIN_OVERLAP, bottom, SNAP_BOTH, SNAP_Y, 1)
        maybe(_x2 - MIN_OVERLAP, bottom, SNAP_BOTH, SNAP_Y, -1)
        maybe(left, _y1 - h + MIN_OVERLAP, SNAP_BOTH, SNAP_X, 1)
        maybe(left, _y2 - MIN_OVERLAP, SNAP_BOTH, SNAP_X, -1)
        maybe(right, _y1 - h + MIN_OVERLAP, SNAP_BOTH, SNAP_X, 1)
        maybe(right, _y2 - MIN_OVERLAP, SNAP_BOTH, SNAP_X, -1)
    return sd["x"], sd["y"]


def overlaps_any(layout, lg, x, y):
    """Would `lg` at (x, y) cover another screen?"""
    lm = layout.layout_mode
    w, h = lg.size(lm)
    r = Rect(x, y, w, h)
    return any(r.overlaps(o.rect(lm)) for o in layout.logicals if o is not lg)


# ── text output ───────────────────────────────────────────────────────────────

def ascii_map(layout, width=64):
    """The screens that are on, drawn to scale."""
    lm = layout.layout_mode
    items = [(l, l.rect(lm)) for l in layout.ordered_logicals()]
    if not items:
        return ["(every screen is off)"]
    max_x = max(r.right for _, r in items)
    max_y = max(r.bottom for _, r in items)
    sx = width / max_x
    sy = sx / 2.2                      # a terminal cell is about twice as tall as wide
    rows = max(int(max_y * sy) + 1, 3)
    canvas = [[" "] * (width + 1) for _ in range(rows)]

    def put(r, c, ch):
        if 0 <= r < rows and 0 <= c <= width:
            canvas[r][c] = ch

    for l, r in items:
        c0, c1 = int(r.x * sx), max(int(r.right * sx) - 1, int(r.x * sx) + 3)
        r0, r1 = int(r.y * sy), max(int(r.bottom * sy) - 1, int(r.y * sy) + 2)
        for c in range(c0, c1 + 1):
            put(r0, c, "─")
            put(r1, c, "─")
        for rr in range(r0, r1 + 1):
            put(rr, c0, "│")
            put(rr, c1, "│")
        put(r0, c0, "┌"); put(r0, c1, "┐"); put(r1, c0, "└"); put(r1, c1, "┘")
        inner = c1 - c0 - 1
        lines = [l.label + (" ★" if l.primary else ""),
                 str(l.monitors[0].mode),
                 ", ".join(m.connector for m in l.monitors)]
        for i, text in enumerate(lines):
            rr = r0 + 1 + i
            if rr >= r1 or inner < 2:
                break
            text = text[:inner]
            start = c0 + 1 + (inner - len(text)) // 2
            for j, ch in enumerate(text):
                put(rr, start + j, ch)
    return ["".join(row).rstrip() for row in canvas]


def describe(layout, numbered=True):
    """Lines for 'gnome-monitor show'."""
    lines = []
    mons = layout.monitors()
    lm = layout.layout_mode
    w_conn = max([len(m.connector) for m in mons] + [9])
    w_name = max([len(m.name) for m in mons] + [7])
    for i, m in enumerate(mons, 1):
        l = layout.logical_of(m)
        num = f"{i:>2}  " if numbered else ""
        if l:
            r = l.rect(lm)
            extra = []
            if l.primary:
                extra.append("main")
            if abs(l.scale - 1) > 1e-3:
                extra.append(f"scale {l.scale:g}")
            if l.transform:
                extra.append(TRANSFORMS[l.transform])
            if len(l.monitors) > 1:
                extra.append("mirrored")
            lines.append(f"{num}{m.connector:<{w_conn}}  {m.name:<{w_name}}  "
                         f"{str(m.mode):<24}  at {r.x},{r.y}  {' '.join(extra)}".rstrip())
        else:
            lines.append(f"{num}{m.connector:<{w_conn}}  {m.name:<{w_name}}  off")
    return lines
