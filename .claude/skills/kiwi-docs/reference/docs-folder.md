# The docs/ folder

`docs/` holds the full documentation of a repository. It is read in two places:
on GitHub, where each page renders on its own, and on kiwi-network.eu, which
copies the folder into the site. Both work if you follow these rules.

## Layout

```
docs/
  README.md        the index: what the tool is, and a table of the pages
  kiwi-docs.yml    the pages in menu order, with their menu titles
  install.md       one page per task or topic
  usage.md
  …
  images/          screenshots and diagrams the pages use (optional)
  install.de.md    a translation, next to its page (optional)
```

- **`docs/README.md`** is the index GitHub shows when someone opens the folder.
  Start from [../templates/docs/README.md](../templates/docs/README.md): one
  paragraph on what the tool is, then a table of the pages with who each one is
  for. Keep it to that. The site does not show this file; it shows its own
  translated overview page in its place, so nothing else may live only here.
- **`docs/kiwi-docs.yml`** lists every page in menu order with its menu title.
  The site builds its menu from it. Start from
  [../templates/docs/kiwi-docs.yml](../templates/docs/kiwi-docs.yml). Every
  page in the folder must be listed, and every listed page must exist.
- **Pages** are lower-case file names with hyphens (`app-authors.md`). One
  page per task or topic, so a reader can find it from the menu. Typical
  pages: `install.md`, `usage.md`, `configuration.md`, `security.md`,
  `troubleshooting.md`, `development.md`; and for tools others build on,
  pages for authors (`app-authors.md`, `writing-a-plugin.md`).
- **Translations** are optional: `page.de.md` next to `page.md`, for de, fr,
  es, it, nl, pl and pt. A translation must have the same headings in the same
  order, each ending with the English anchor (`## Installieren { #install }`),
  and the same links and code. The site falls back to English for any page
  without a translation.

## Links

- **Between pages: relative links** to the `.md` file, with an anchor if
  needed: `[Security](security.md#when-you-type-a-password)`. Link to the index
  as `README.md`. The checker verifies every file and anchor.
- **To files in the repository outside `docs/`: full GitHub URLs**, for
  example `https://github.com/derlocke-ng/kiwi-updater/blob/main/templates/kiwi.manifest`.
  A relative link out of `docs/` (`../install.sh`) works on GitHub but breaks
  on the site, so the checker rejects it.
- **To other Kiwi tools: their page on kiwi-network.eu**, for example
  `https://kiwi-network.eu/docs/clients/kiwi-proxy/`.
- **Never** links that start with `/`.

## Headings and anchors

Anchors are made from the heading text (lower case, punctuation removed,
spaces become hyphens): `## When you type a password` → `#when-you-type-a-password`.
Other pages and the site link to these anchors, so do not rename a heading
casually. If you must, keep the old anchor: `## New wording { #old-anchor }`.

## Images

Put images in `docs/images/` and link them relatively:
`![Kiwi Apps showing updates](images/kiwi-gui-updates.png)`. Use SVG for
diagrams, PNG for screenshots, and write real alt text. No images from other
servers.

## How the site uses the folder

kiwi-network.eu rebuilds every day and on every change to kiwi-network. Each
time it:

1. looks up the repository's **latest release tag** (`vX.Y.Z`, no pre-releases),
2. copies `docs/` at that tag into the site, under the tool's overview page
   (for example `/docs/desktop/kiwi-updater/install/`),
3. builds the menu from `kiwi-docs.yml`,
4. checks every link, and skips the whole folder if one is broken, keeping the
   overview page.

So: a docs change reaches the site with the next release. Run the checker
before you tag.
