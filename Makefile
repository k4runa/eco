# eco Makefile

.PHONY: help install install-user uninstall clean run

help:
	@echo "eco - available targets:"
	@echo "  make install    - install eco with pipx (isolated, recommended)"
	@echo "  make install-user - install into the user site with pip"
	@echo "  make uninstall  - remove eco"
	@echo "  make run        - run from the source tree (./main.py --help)"
	@echo "  make clean      - remove build/cache artifacts"

# Recommended: pipx gives an isolated environment and a clean `eco` command.
install:
	@command -v pipx >/dev/null 2>&1 || { \
		echo "pipx not found. Install it with: sudo pacman -S python-pipx"; exit 1; }
	pipx install --force .
	@echo ""
	@echo "Installed. Run 'eco --help' to get started."

# Fallback: user-site install (Arch marks the base env externally-managed, so
# --break-system-packages is required for a user install there).
install-user:
	pip install --user --break-system-packages .
	@echo ""
	@echo "Installed to the user site. Ensure ~/.local/bin is on your PATH."

uninstall:
	@command -v pipx >/dev/null 2>&1 && pipx uninstall eco || \
		pip uninstall -y eco || true

run:
	./main.py --help

clean:
	find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.py[co]' -delete
	rm -rf build dist *.egg-info
	@echo "Clean."
