#!/usr/bin/env python3
"""Check the README.md and docs/ folder of a Kiwi Network repository.

Usage:
  check-docs.py [REPO]                 check README.md and docs/ (default: .)
  check-docs.py REPO --docs-only       check only docs/ (used by kiwi-network.eu)
  check-docs.py REPO --no-upstream     do not look for a newer version of this guide

Errors make the exit code 1. Warnings are printed but do not fail.
Standard library only, so it runs anywhere Python 3.8+ is installed.
"""
import html
import os
import re
import sys
import unicodedata
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UPSTREAM_VERSION = ("https://raw.githubusercontent.com/derlocke-ng/kiwi-network/main/"
                    "plugins/kiwi-docs/skills/kiwi-docs/VERSION")
LANGS = ("de", "fr", "es", "it", "nl", "pl", "pt")
HYPE = re.compile(r"\b(simply|seamless(ly)?|powerful|blazing(ly)?|robust|leverag\w*|"
                  r"utili[sz]e|super[- ]easy|effortless(ly)?|just works|out of the box)\b", re.I)
README_MAX_WARN, README_MAX_FAIL = 100, 150

errors, warnings = [], []


def err(where, msg):
    errors.append(f"{where}: {msg}")


def warn(where, msg):
    warnings.append(f"{where}: {msg}")


# ---------- Markdown helpers (enough for docs, not a full parser) ----------

FENCE = re.compile(r"^\s*(```|~~~)")


def prose_lines(text):
    """Yield (line_number, line) outside fenced code blocks, inline code removed."""
    in_fence = False
    for n, line in enumerate(text.split("\n"), 1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            yield n, line


def plain(md):
    md = re.sub(r"\s*\{\s*#[^}]*\}\s*$", "", md)
    md = re.sub(r"`([^`]*)`", r"\1", md)
    md = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", md)
    md = re.sub(r"<[^>]+>", "", md)
    md = re.sub(r"(\*\*|__|\*|_)(.+?)\1", r"\2", md)
    return html.unescape(md).strip()


def slug_site(text):
    """Python-Markdown's toc slugify, as MkDocs uses it."""
    v = unicodedata.normalize("NFKD", plain(text)).encode("ascii", "ignore").decode("ascii")
    v = re.sub(r"[^\w\s-]", "", v).strip().lower()
    return re.sub(r"[-\s]+", "-", v)


def slug_github(text):
    v = plain(text).lower()
    v = re.sub(r"[^\w\- ]", "", v)
    return v.replace(" ", "-")


def headings(text):
    """[(level, raw_text, line)] outside code blocks."""
    out = []
    for n, line in prose_lines(text):
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if m:
            out.append((len(m.group(1)), m.group(2), n))
    return out


def anchors(text):
    """Anchors a page offers on the site (with MkDocs' _1 suffixes) and on GitHub."""
    site, gh, seen_s, seen_g = set(), set(), {}, {}
    for _, raw, _ in headings(text):
        m = re.search(r"\{\s*#([^\s}]+)\s*\}\s*$", raw)
        s = m.group(1) if m else slug_site(raw)
        g = slug_github(raw)
        for slug, seen, bucket in ((s, seen_s, site), (g, seen_g, gh)):
            k = seen.get(slug, 0)
            bucket.add(slug if k == 0 else f"{slug}_{k}" if bucket is site else f"{slug}-{k}")
            seen[slug] = k + 1
    for _, line in prose_lines(text):
        for a in re.findall(r'(?:id|name)="([^"]+)"', line):
            site.add(a)
            gh.add(a)
    return site, gh


LINK = re.compile(r"(!?)\[([^\]]*)\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")


def links(text):
    for n, line in prose_lines(text):
        line = re.sub(r"`[^`]*`", "", line)
        for m in LINK.finditer(line):
            yield n, m.group(1) == "!", m.group(3)
        for m in re.finditer(r'(?:href|src)="([^"]+)"', line):
            yield n, False, m.group(1)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


# ---------- checks ----------

def check_links(path, text, root, inside):
    """root: folder links may not leave (docs/ or the repo); inside: label for messages."""
    rel = os.path.relpath(path)
    for n, is_img, url in links(text):
        where = f"{rel}:{n}"
        if re.match(r"^[a-z][a-z0-9+.-]*:", url, re.I):
            if url.startswith("http://"):
                warn(where, f"plain http link {url}; use https")
            if is_img:
                err(where, f"image from another server ({url}); put it in docs/images/")
            continue
        if url.startswith("/"):
            err(where, f"link starts with '/' ({url}); use a relative link or a full https URL")
            continue
        target, _, anchor = url.partition("#")
        tpath = os.path.normpath(os.path.join(os.path.dirname(path), target)) if target else path
        if os.path.commonpath([os.path.abspath(tpath), os.path.abspath(root)]) != os.path.abspath(root):
            err(where, f"link leaves {inside} ({url}); link files elsewhere in the repository "
                       f"with a full https://github.com/… URL")
            continue
        if not os.path.exists(tpath):
            err(where, f"link target does not exist: {url}")
            continue
        if os.path.isdir(tpath):
            warn(where, f"link to a folder ({url}); link to its README.md or a page")
            continue
        if anchor and tpath.endswith(".md"):
            site, gh = anchors(read(tpath))
            if anchor not in site:
                err(where, f"anchor #{anchor} not found in {os.path.relpath(tpath)}")
            elif anchor not in gh:
                warn(where, f"anchor #{anchor} works on kiwi-network.eu but not on GitHub; "
                            f"simplify the heading or link without the anchor")


def check_style(path, text):
    rel = os.path.relpath(path)
    for n, line in prose_lines(text):
        bare = re.sub(r"`[^`]*`", "", line)
        bare = re.sub(r"\]\([^)]*\)", "]", bare)
        m = HYPE.search(bare)
        if m:
            warn(f"{rel}:{n}", f"'{m.group(0)}' — say what it does instead (voice.md, rule 6)")
        if re.search(r"\b(TODO|TBD|FIXME|coming soon)\b", bare, re.I):
            warn(f"{rel}:{n}", "placeholder text left in the docs")


def check_headings(path, text, need_h1=True):
    rel = os.path.relpath(path)
    hs = headings(text)
    h1 = [h for h in hs if h[0] == 1]
    if need_h1:
        if not hs or hs[0][0] != 1:
            err(rel, "the page must start with one '# ' heading")
        if len(h1) > 1:
            err(f"{rel}:{h1[1][2]}", "more than one '# ' heading on the page")
    prev = 1
    for lvl, raw, n in hs:
        if lvl > prev + 1:
            warn(f"{rel}:{n}", f"heading level jumps from {prev} to {lvl}")
        prev = lvl


def check_readme(repo):
    path = os.path.join(repo, "README.md")
    if not os.path.exists(path):
        err("README.md", "missing")
        return
    text = read(path)
    lines = text.rstrip("\n").split("\n")
    if len(lines) > README_MAX_FAIL:
        err("README.md", f"{len(lines)} lines; keep it under {README_MAX_WARN} and move details to docs/")
    elif len(lines) > README_MAX_WARN:
        warn("README.md", f"{len(lines)} lines; aim for under {README_MAX_WARN} (readme.md)")
    check_headings(path, text)
    hs = [plain(h[1]).lower() for h in headings(text) if h[0] == 2]
    first_h2 = next((n for n, line in enumerate(lines) if line.startswith("## ")), len(lines))
    intro = "\n".join(lines[1:first_h2]).strip()
    if len(re.sub(r"\s+", " ", intro)) < 80:
        err("README.md", "start with a paragraph that says what the tool is and who it is for")
    if not any(h.startswith(("install", "use", "run", "get started", "getting started")) for h in hs):
        warn("README.md", "no '## Install' section (or '## Use' / '## Run …' if it is not installed)")
    if "documentation" not in hs and os.path.isdir(os.path.join(repo, "docs")):
        err("README.md", "no '## Documentation' section linking to the pages in docs/")
    if not any(h.startswith(("license", "licence")) for h in hs):
        err("README.md", "no '## License' section")
    if any(h.startswith(("roadmap", "planned", "todo")) for h in hs):
        warn("README.md", "a roadmap/planned section; put real plans in docs/ or an issue (readme.md)")
    if not any(os.path.exists(os.path.join(repo, f)) for f in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING")):
        warn("README.md", "the repository has no LICENSE file")
    if re.search(r"img\.shields\.io|badge\.fury|travis-ci", text):
        warn("README.md", "badges load from third-party servers; state the facts as text")
    check_links(path, text, repo, "the repository")
    check_style(path, text)


def parse_nav(path):
    pages, ok = [], True
    for n, line in enumerate(read(path).split("\n"), 1):
        s = line.split("#", 1)[0].rstrip() if not line.lstrip().startswith("- ") else line.rstrip()
        if not s.strip() or s.strip() == "pages:":
            continue
        m = re.match(r"^\s*-\s+([A-Za-z0-9._/-]+\.md)\s*:\s*(.+?)\s*$", s)
        if not m:
            err(f"docs/kiwi-docs.yml:{n}", f"expected '  - page.md: Menu title', got: {line.strip()}")
            ok = False
            continue
        pages.append((m.group(1), m.group(2).strip("'\"")))
    return pages, ok


def check_docs(repo):
    docs = os.path.join(repo, "docs")
    if not os.path.isdir(docs):
        warn("docs/", "no docs/ folder; everything beyond the first five minutes belongs there (docs-folder.md)")
        return
    md = sorted(os.path.relpath(os.path.join(d, f), docs)
                for d, _, fs in os.walk(docs) for f in fs if f.endswith(".md"))
    trans = [p for p in md if re.search(r"\.[a-z]{2}\.md$", p)]
    for t in trans:
        lang = t.rsplit(".", 2)[-2]
        if lang not in LANGS:
            warn(f"docs/{t}", f"'{lang}' is not one of the site's languages ({', '.join(LANGS)})")
        elif re.sub(r"\.[a-z]{2}\.md$", ".md", t) not in md:
            err(f"docs/{t}", "translation without an English page next to it")
    english = [p for p in md if p not in trans]
    if "README.md" not in english:
        err("docs/README.md", "missing: the index page with a table of the pages")
    navf = os.path.join(docs, "kiwi-docs.yml")
    listed = []
    if not os.path.exists(navf):
        err("docs/kiwi-docs.yml", "missing: list the pages in menu order (templates/docs/kiwi-docs.yml)")
    else:
        nav, _ = parse_nav(navf)
        listed = [p for p, _ in nav]
        for p in listed:
            if p == "README.md":
                err("docs/kiwi-docs.yml", "README.md is the index; do not list it")
            elif p not in english:
                err("docs/kiwi-docs.yml", f"lists {p}, which does not exist")
        for p in english:
            if p != "README.md" and p not in listed:
                err("docs/kiwi-docs.yml", f"does not list {p}")
        if len(set(listed)) != len(listed):
            err("docs/kiwi-docs.yml", "a page is listed twice")
    for p in md:
        path = os.path.join(docs, p)
        text = read(path)
        check_headings(path, text)
        check_links(path, text, docs, "docs/")
        if p not in trans:
            check_style(path, text)
    idx = os.path.join(docs, "README.md")
    if os.path.exists(idx) and listed:
        targets = {os.path.normpath(u.split("#")[0]) for _, _, u in links(read(idx)) if not re.match(r"^[a-z]+:", u)}
        for p in listed:
            if os.path.normpath(p) not in targets and os.path.exists(os.path.join(docs, p)):
                warn("docs/README.md", f"the index does not link to {p}")
    for t in trans:
        base = re.sub(r"\.[a-z]{2}\.md$", ".md", t)
        if base in md:
            a = [h[0] for h in headings(read(os.path.join(docs, base)))]
            b = [h[0] for h in headings(read(os.path.join(docs, t)))]
            if a != b:
                err(f"docs/{t}", "headings differ from the English page (levels or count)")


def check_ignored(repo):
    """The guide copy and docs/ must be committed; a .gitignore rule can silently hide them."""
    import subprocess
    for rel in (".claude/skills/kiwi-docs/SKILL.md", "docs/kiwi-docs.yml", "docs/README.md"):
        if not os.path.exists(os.path.join(repo, rel)):
            continue
        try:
            r = subprocess.run(["git", "-C", repo, "check-ignore", "-v", rel], capture_output=True, text=True)
        except OSError:
            return
        if r.returncode == 0:
            rule = r.stdout.split("\t")[0]
            err(rel, f"is ignored by git ({rule}), so it will not be committed. For .claude/ use "
                     f"'.claude/*' plus '!.claude/skills/' in .gitignore")


def check_upstream():
    try:
        mine = read(os.path.join(HERE, "..", "VERSION")).strip()
        with urllib.request.urlopen(UPSTREAM_VERSION, timeout=5) as r:
            theirs = r.read().decode().strip()
    except Exception:
        return
    key = lambda v: [int(x) for x in re.findall(r"\d+", v)]
    if key(theirs) > key(mine):
        warn("kiwi-docs guide", f"this copy is {mine}, kiwi-network has {theirs}; update it (SKILL.md, "
                                f"'Keeping this guide current')")


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    repo = os.path.abspath(args[0] if args else ".")
    if not os.path.isdir(repo):
        print(f"not a folder: {repo}")
        return 2
    cwd = os.getcwd()
    os.chdir(repo)
    if "--docs-only" not in argv:
        check_readme(repo)
    check_docs(repo)
    if "--docs-only" not in argv:
        check_ignored(repo)
    if "--no-upstream" not in argv:
        check_upstream()
    os.chdir(cwd)
    for w in warnings:
        print(f"warning  {w}")
    for e in errors:
        print(f"ERROR    {e}")
    print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
