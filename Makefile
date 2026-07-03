# anypc — one-time installer for the systemd user services.
#
# On a fresh server, from the cloned repo (any path):
#   sudo make install      # place code at /opt/anypc, install deps, set up units
#
# Then, as your normal user, open a new shell (or `source ~/.bashrc`) and use
# the installed `anypc` helper from any directory:
#   anypc launch           # start both services
#   anypc {stop|restart|status|logs}
#
# To auto-start the services at boot (they run without a login session):
#   sudo loginctl enable-linger $USER
#   systemctl --user enable anypc-vnc anypc-server
#   systemctl --user enable ngrok-ssh    # only if installed with WITH_NGROK=1

APP_DIR  := /opt/anypc
SERVICES := anypc-vnc.service anypc-server.service

# Optional ngrok SSH tunnel service. Off by default; opt in with:
#   sudo make install WITH_NGROK=1
# Requires ngrok on the PATH with a configured authtoken.
WITH_NGROK ?= 0
ifeq ($(WITH_NGROK),1)
SERVICES += ngrok-ssh.service
endif

# The unprivileged user that owns and runs the app. Under `sudo` this is the
# invoking user (SUDO_USER); otherwise the current user.
RUN_USER := $(or $(SUDO_USER),$(USER))
RUN_HOME := $(shell getent passwd $(RUN_USER) | cut -d: -f6)
UNIT_DIR := $(RUN_HOME)/.config/systemd/user

.PHONY: install

# One-time setup — run with sudo from the cloned repo. Copies the code to
# /opt/anypc, installs system + Python deps and the VNC desktop, installs the
# systemd user unit files and the `anypc` shell helper, then hands ownership
# to $(RUN_USER).
install:
	mkdir -p $(APP_DIR)
	[ "$(CURDIR)" = "$(APP_DIR)" ] || cp -a . $(APP_DIR)/
	$(APP_DIR)/scripts/install_deps.sh
	mkdir -p $(UNIT_DIR)
	cp $(addprefix $(APP_DIR)/systemd/,$(SERVICES)) $(UNIT_DIR)/
	chown -R $(RUN_USER): $(APP_DIR) $(RUN_HOME)/.config/systemd
