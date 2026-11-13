# The README

The README is the first thing people see on GitHub. It answers five questions
quickly and sends everything else to `docs/`. Keep it under about 100 lines;
the checker warns above 100 and fails above 150.

## Shape

Start from [../templates/README.md](../templates/README.md). In this order:

1. **`# name`**: the repository or tool name, nothing else.
2. **One or two paragraphs**: what it is, who it is for, what problem it
   removes. Where it belongs in Kiwi Network, in one sentence.
3. **A short facts list** (optional): latest release, license, supported
   systems in one line, where it is in the Kiwi catalog. No badges that load
   from third-party servers.
4. **`## Install`**: the shortest working way, usually
   `kiwi install <name>`, plus the alternative from a checkout. If it is not
   installed (a library, a web app, a list), call the section what the reader
   does instead: `## Use`, `## Run a hub`.
5. **`## Quick start`** (when there is something to start): three to ten lines
   that show the tool doing its main job.
6. **`## Documentation`**: a list of the `docs/` pages with one line each, and
   the page on kiwi-network.eu (for example
   `https://kiwi-network.eu/docs/desktop/kiwi-updater/`).
7. **`## License`**: the SPDX name (`GPL-3.0-or-later`, `MIT`, `CC BY-SA 4.0`)
   and the file it is in. It must match the `LICENSE` file.

Optional, short: `## Status` (known gaps, what is experimental), `## Contributing`
(one paragraph and a link to `docs/development.md`).

## What does not belong in the README

- Option tables, every command, configuration reference, security details,
  architecture, development and release steps, long troubleshooting: those are
  `docs/` pages.
- A "planned" or "roadmap" list. Put real plans in `docs/` or an issue, and
  leave ideas out.
- History ("in version 1.2 we changed …"): that is `CHANGELOG.md`.
- Anything the code does not do at the latest release.
