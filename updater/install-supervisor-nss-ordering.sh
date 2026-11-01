#!/bin/bash
#
# Gives an existing install the supervisor startup ordering a fresh install gets
# from pifire_install_supervisor_ordering. Run from the updater manifest as
# root (sudo bash ...), so the drop-in and daemon-reload need no extra sudoers
# grants. The drop-in explains the boot failure it prevents:
# auto-install/systemd/supervisor-nss-ordering.conf.

set -u

export PATH="${PATH:-/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${PIFIRE_REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
LOG="${PIFIRE_UPDATER_LOG:-/dev/null}"
if [[ $EUID -eq 0 ]]; then
	SUDO=""
else
	SUDO="sudo"
fi
# shellcheck source=../auto-install/pifire-install-common.sh
source "$REPO_ROOT/auto-install/pifire-install-common.sh"

# Fedora ships supervisord.service, Debian supervisor.service. Order whichever
# this host has; a host with neither has nothing to fix.
found=0
for unit in supervisord supervisor; do
	if systemctl list-unit-files --no-legend "$unit.service" 2>/dev/null | grep -q "^$unit\.service"; then
		pifire_install_supervisor_ordering "$unit" "$REPO_ROOT" || exit 1
		found=1
	fi
done
if [[ $found -eq 0 ]]; then
	echo "No supervisor systemd unit found; nothing to order"
fi
exit 0
