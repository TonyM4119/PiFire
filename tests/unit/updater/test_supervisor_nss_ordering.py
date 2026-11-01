from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[3]
MIGRATION = REPOSITORY / "updater" / "install-supervisor-nss-ordering.sh"
COMMON = REPOSITORY / "auto-install" / "pifire-install-common.sh"
DROP_IN = REPOSITORY / "auto-install" / "systemd" / "supervisor-nss-ordering.conf"
INSTALLERS = [
    REPOSITORY / "auto-install" / name
    for name in ("install-fedora.sh", "install-debian.sh", "install.sh", "pifire-dietpi.sh")
]


def _write_executable(path: Path, body: str) -> None:
    path.write_text("#!/bin/sh\nset -eu\n" + body)
    path.chmod(0o755)


def _migration_tree(tmp_path: Path, present_units: str) -> tuple[Path, dict[str, str], Path, Path]:
    repo = tmp_path / "pifire"
    (repo / "updater").mkdir(parents=True)
    shutil.copy2(MIGRATION, repo / "updater" / MIGRATION.name)
    (repo / "auto-install" / "systemd").mkdir(parents=True)
    shutil.copy2(COMMON, repo / "auto-install" / COMMON.name)
    shutil.copy2(DROP_IN, repo / "auto-install" / "systemd" / DROP_IN.name)

    systemd_root = tmp_path / "etc" / "systemd" / "system"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "commands.log"
    _write_executable(fake_bin / "sudo", 'printf "sudo %s\\n" "$*" >>"$COMMAND_LOG"\nexec "$@"\n')
    # list-unit-files answers for the units this host "has"; every other verb
    # is only recorded, so a restart would show up in the log.
    _write_executable(
        fake_bin / "systemctl",
        'printf "systemctl %s\\n" "$*" >>"$COMMAND_LOG"\n'
        'if [ "$1" = "list-unit-files" ]; then\n'
        "  for unit in $PRESENT_UNITS; do\n"
        '    [ "$unit.service" = "$3" ] && echo "$unit.service enabled enabled"\n'
        "  done\n"
        "fi\n"
        "exit 0\n",
    )
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:/usr/bin:/bin",
        "COMMAND_LOG": str(log),
        "PRESENT_UNITS": present_units,
        "PIFIRE_REPO_ROOT": str(repo),
        "PIFIRE_SYSTEMD_ROOT": str(systemd_root),
    }
    return repo, env, systemd_root, log


def _run(repo: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/bash", str(repo / "updater" / MIGRATION.name)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _directives(text: str) -> dict[str, str]:
    lines = (line for line in text.splitlines() if "=" in line and not line.startswith("#"))
    return dict(line.split("=", 1) for line in lines)


@pytest.mark.parametrize("unit", ["supervisord", "supervisor"])
def test_migration_orders_the_host_supervisor_unit_after_user_lookups(tmp_path: Path, unit: str) -> None:
    repo, env, systemd_root, log = _migration_tree(tmp_path, unit)

    completed = _run(repo, env)

    assert completed.returncode == 0, completed.stderr
    drop_in = systemd_root / f"{unit}.service.d" / "pifire-nss-ordering.conf"
    assert drop_in.read_text() == DROP_IN.read_text()
    assert oct(drop_in.stat().st_mode & 0o777) == "0o644"
    other = "supervisor" if unit == "supervisord" else "supervisord"
    assert not (systemd_root / f"{other}.service.d").exists()
    commands = log.read_text()
    assert "systemctl daemon-reload" in commands
    assert "restart" not in commands
    assert "supervisorctl" not in commands


def test_migration_is_a_no_op_without_a_supervisor_unit(tmp_path: Path) -> None:
    repo, env, systemd_root, log = _migration_tree(tmp_path, "")

    completed = _run(repo, env)

    assert completed.returncode == 0, completed.stderr
    assert "nothing to order" in completed.stdout
    assert not systemd_root.exists()
    assert "daemon-reload" not in log.read_text()


def test_drop_in_only_orders_and_never_requires_sssd() -> None:
    directives = _directives(DROP_IN.read_text())

    assert set(directives) == {"After", "Wants", "Restart", "RestartSec"}
    assert "sssd.service" in directives["After"].split()
    assert "nss-user-lookup.target" in directives["After"].split()
    assert directives["Wants"].split() == ["nss-user-lookup.target"]
    assert directives["Restart"] == "on-failure"


def test_every_fresh_installer_orders_supervisor_before_starting_it() -> None:
    for installer in INSTALLERS:
        text = installer.read_text()
        unit = "supervisord" if installer.name == "install-fedora.sh" else "supervisor"
        call = f"pifire_install_supervisor_ordering {unit} /usr/local/bin/pifire"
        assert call in text, installer
        # The sudoers heredoc also names "systemctl restart <unit>"; only the
        # $SUDO-prefixed line is the installer actually starting the service.
        start = max(text.find(f"$SUDO systemctl restart {unit}"), text.find("$SUDO service supervisor start"))
        assert start >= 0, installer
        assert text.find(call) < start, installer


def test_manifest_migrates_existing_installs_as_root() -> None:
    manifest = json.loads((REPOSITORY / "updater" / "updater_manifest.json").read_text())
    entry = next(entry for entry in manifest["versions"] if entry["version"] == "1.31.1" and entry["build"] == 136)
    commands = [command for section in entry["dependencies"].values() for command in section["command_list"]]

    assert commands == [["sudo", "bash", "/usr/local/bin/pifire/updater/install-supervisor-nss-ordering.sh"]]
    assert "acados_bootstrap" not in entry
    assert entry["reboot_required"] is False
    assert MIGRATION.exists()
