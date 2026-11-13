# The Kiwi voice

Kiwi docs are read by people who have never seen the project, and they are
translated into seven languages. Text that is clipped, built on metaphors or
full of unexplained words is hard to follow and turns into nonsense when it is
translated. The kiwi-network site was rewritten in November 2026 because its
texts had exactly these problems. Write so that this never has to happen again.

## What Kiwi Network is

Every page should fit into this picture. Kiwi Network is an open-source Linux
environment that people run themselves, for their whole digital life and work.
It has three parts:

- **The network** (kiwi-server, kiwi-modules, kiwi-stack): your servers and
  devices in one private WireGuard network. One server, the *master*, is the
  only machine reachable from the Internet. The *nodes* at home or in the office
  run your services. Machines install themselves, update themselves, back up
  every night, unlock their encrypted disks, and can be rebuilt from the fleet
  file and the backup. The design assumes break-ins, outages and lost hardware.
- **Hubs** (kiwi-framework, Armory, kiwi-web-catalog): software with which any
  community runs its own hub (an open marketplace, a feed, chat, file sharing)
  in the browser, synchronised over nostr relays, with no central platform.
  Armory is the first hub, not the point of the project.
- **The desktop** (kiwi-updater and the apps): a Fedora Atomic workstation that
  is set up automatically and gets its apps from git catalogs. kiwi-proxy,
  kiwi-custodia and kiwi-fox are for people who work in many clients' networks:
  each client's VPN or SOCKS connection gets its own isolated container.

## Rules

1. **Start with what it is for.** The first paragraph of a README and of every
   page says what the thing is, who needs it and what problem it removes. Then
   the details.
2. **Say literally what happens.** Use the plain verb for the technical event.

   | Not | But |
   |---|---|
   | nodes dial out to the master | nodes open the connection to the master themselves |
   | a master at the gate · one door to the Internet | the only machine reachable from the Internet · one open port |
   | Pi-hole lives in the WireGuard namespace and comes back with it | Pi-hole shares the WireGuard server's network namespace, so it is restarted with it |
   | UDP leaves nowhere | UDP is not forwarded |
   | DNS cannot wander off | DNS queries cannot bypass the tunnel |
   | if the gateway dies | if the gateway stops |
   | the daemon owns the firewall | only the daemon changes the firewall |
   | apart stays apart | clients are kept separate |

3. **Full sentences.** No telegraph style ("A CLI and a GTK app. Proven on
   hardware." → "It has a command-line tool and a desktop app, and it has been
   tested on real hardware."). List items may be short, but each must make
   sense on its own.
4. **Explain a term where a page first uses it**, in a few words: mesh, double
   hop, fail-closed, network namespace, exit, quadlet, Tang, relay,
   distribution, mount, catalog, scope … Then use that one word every time. Do
   not swap synonyms.
5. **Keep the project's own words**: master, node, fleet, fleet file, role,
   preset, module, hub, distribution, space, mount, exit, gateway, box,
   catalog, scope. Machine names in examples are fruit: masters are fruit
   dishes (sorbet, crumble, compote), nodes are fruits (papaya, lychee, quince).
6. **No hype.** Not "simply", "just", "easy", "seamless", "powerful", "robust",
   "blazing", "leverage". Say what it does and let that speak.
7. **State status and limits exactly**, with these words and no others:
   *planned* (decided, not started), *designed, not built* (a design exists),
   *experimental* or *to try out* (works, not proven), *tested on real
   hardware* / *tested on X* (only if it was), *known gaps*. Never soften a
   limit and never promise a date.
8. **Address the reader as "you".** Calm, concrete, friendly, like a colleague
   who explains it once and well.
9. **Normal sentence length.** Two clear sentences beat one dense one. Avoid
   chains of nouns, stacked parentheses, and colons or semicolons used to
   squeeze two thoughts into one.
10. **Write for translation.** No puns, no idioms that only work in English,
    no jokes in headings. Headings are plain descriptions ("Install",
    "Back up a node"), not slogans.

## Formatting

- One `#` heading per page, at the top. `##` for sections, `###` below that.
  Do not skip a level.
- Commands, file names, options, keys and values in `code`. Longer commands in
  fenced blocks with a language (`bash`, `yaml`, `ini` …). Comments inside a
  block are short prose and may be translated.
- Tables for reference data (options, supported systems, commands). Each cell a
  full phrase or sentence.
- Admonitions are not portable to GitHub, so use them sparingly; a bold lead
  word ("**Warning.** The ISO wipes …") works everywhere.
- Wrap prose at about 80 columns; it keeps diffs small.
