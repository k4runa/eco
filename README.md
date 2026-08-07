# 🌱 eco

[![Version](https://img.shields.io/badge/version-1.0.0-4ec9b0.svg)](https://github.com/k4runa/eco)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-yellow.svg)](https://www.python.org/)
[![Arch](https://img.shields.io/badge/Arch%20Linux-1793D1.svg)](https://archlinux.org/)

One command to update **Pacman**, an **AUR helper** (paru/yay), **Flatpak** and your
tracked **Git repos** — behind a single, honest, animated terminal UI. Update all
of them, or just the one you care about: `eco --update aur`.

Checks run read-only and in parallel behind a live status board; you then pick
what to apply (`all`, or `pacman aur`, or `none`) and updates run
one at a time with the real tool attached to your terminal, so prompts and output
behave normally and the result you see is the one pacman/yay/git actually reported.

## Install

Needs Arch (`pacman`), Python 3.9+, `pacman-contrib` and `rich`
(`sudo pacman -S pacman-contrib python-rich`). yay/paru, flatpak and
notify-send are optional.

```bash
git clone https://github.com/k4runa/eco.git && cd eco
make install          # via pipx (sudo pacman -S python-pipx), or:
make install-user     # into the user site, or just run ./main.py
```

## Usage

```bash
eco --update                 # update everything (asks first)
eco --update aur             # update only the AUR
eco --update pacman flatpak  # update only these, ignoring the config
eco --update --dry-run       # preview only, change nothing
eco --update --noconfirm     # no prompts

eco --add-repo ~/dotfiles    # track / list / untrack git repos
eco --list-repos
eco --remove-repo ~/dotfiles

eco --clear-cache pacman     # paccache -rk1 (or: flatpak → unused runtimes)
eco --clean-orphans          # remove orphans (asks first)

eco --schedule daily         # systemd timer at 02:00 (or weekly / --unschedule)
eco --stats                  # run history
eco --config                 # show settings
```

## Configuration

`~/.config/eco/config.json` — small on purpose, every field is honoured:

```json
{
  "sources": ["pacman", "aur", "flatpak", "git"],
  "excluded_packages": [],
  "webhook_url": null,
  "aur_helper": null
}
```

- **sources** — the default set to update; drop an entry to skip it (missing tools
  skip themselves). Naming sources on the command line (`eco --update aur`)
  overrides this for that run.
- **excluded_packages** — passed straight to pacman/AUR as `--ignore`.
- **webhook_url** — set it to also notify a Discord/Slack webhook (payload auto-detected).
- **aur_helper** — `paru` or `yay`; `null` auto-detects (paru first, then yay).

Edit the file or use `eco --set key=value` (comma-separate lists):

```bash
eco --set sources=pacman,aur
eco --set excluded_packages=linux,nvidia
eco --set aur_helper=yay          # or: aur_helper=none to auto-detect again
```

`--noconfirm`/`--dry-run` are CLI-only; desktop notifications are on when
`notify-send` is installed. Old `enable_*` configs migrate automatically.

**Hooks:** executable scripts in `~/.config/eco/hooks/{pre,post}-update/` run in
name order around updates.

> eco takes no system backups. For real rollback use **snapper**/**Timeshift**.

## License

MIT — see [LICENSE](LICENSE). By [**k4runa**](https://github.com/k4runa). ⭐ if it helps.
