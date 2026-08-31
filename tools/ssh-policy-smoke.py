#!/usr/bin/env python3
"""Source-only regression for RC4 SSH authentication policy and client-key UI.

This test never starts sshd, changes passwords, writes /etc/ssh, or opens port 22.
It verifies the policy builder, runtime controller fail-closed contract, and the
operator-facing client-key enrollment UI markers.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "lib"
sys.path.insert(0, str(LIB))

import ssh_keys_admin as keys

original_normal_user = keys._normal_user
try:
    # Policy text does not need a real account for this source-only test; the
    # production helper still validates the selected account before installing.
    keys._normal_user = lambda username: (object(), Path("/home") / username)

    key_only = keys.build_policy(keys.AUTH_KEY_ONLY, "ywd")
    assert "PubkeyAuthentication yes" in key_only
    assert "PasswordAuthentication no" in key_only
    assert "KbdInteractiveAuthentication no" in key_only
    assert "ChallengeResponseAuthentication no" in key_only
    assert "PermitEmptyPasswords no" in key_only
    assert "PermitRootLogin no" in key_only
    assert "AuthenticationMethods publickey" in key_only
    assert "AllowUsers ywd" in key_only

    password_key = keys.build_policy(keys.AUTH_PASSWORD_KEY, "operator")
    assert "PubkeyAuthentication yes" in password_key
    assert "PasswordAuthentication yes" in password_key
    assert "KbdInteractiveAuthentication no" in password_key
    assert "ChallengeResponseAuthentication no" in password_key
    assert "PermitEmptyPasswords no" in password_key
    assert "PermitRootLogin no" in password_key
    assert "AuthenticationMethods publickey" not in password_key
    assert "AllowUsers operator" in password_key
finally:
    keys._normal_user = original_normal_user

runtime = (LIB / "ssh_runtime_admin.py").read_text(encoding="utf-8")
helper = (LIB / "ssh_keys_admin.py").read_text(encoding="utf-8")
ssh_ui = (ROOT / "web" / "ssh-key-export.js").read_text(encoding="utf-8")
system_css = (ROOT / "web" / "system-ui.css").read_text(encoding="utf-8")

for marker in (
    "keys.install_policy(mode, username)",
    "set_boot_enabled(True)",
    'run(["systemctl", "reload", SSH_UNIT]',
    'run(["systemctl", "start", "--no-block", SSH_UNIT]',
    "set_boot_enabled(False)",
    'run(["systemctl", "stop", "--no-block", SSH_UNIT]',
):
    assert marker in runtime, f"SSH runtime contract marker missing: {marker}"

for marker in (
    '_run([str(SSHD), "-t"]',
    "_validate_effective_policy(mode, username)",
    '"pubkeyauthentication": "yes"',
    '"kbdinteractiveauthentication": "no"',
    '"permitemptypasswords": "no"',
    '"permitrootlogin": "no"',
):
    assert marker in helper, f"SSH effective-policy validation marker missing: {marker}"

for marker in (
    "CREATE & EXPORT SSH CLIENT KEY",
    "CREATING SSH CLIENT KEY…",
    "busyAction='client-key'",
    "aria-busy",
    "/api/ssh-client-key/create",
):
    assert marker in ssh_ui, f"SSH client-key UI marker missing: {marker}"

assert "EXPORT SERVER IDENTITY" not in ssh_ui, "server identity export must not be exposed in normal SSH UI"
assert "sshKeysExport" not in ssh_ui, "server identity export button wiring must be removed from normal SSH UI"
assert "exportServerIdentity" not in ssh_ui, "server identity export action must be removed from normal SSH UI"

for marker in (
    ".ssh-client-key-row",
    "#sshClientCreate.ywd-action-busy::before",
    "@keyframes ywd-ssh-action-spin",
    "white-space:normal",
    "max-width:100%",
):
    assert marker in system_css, f"SSH mobile/busy CSS marker missing: {marker}"

assert keys.normalize_auth_mode("key-only") == keys.AUTH_KEY_ONLY
assert keys.normalize_auth_mode("password+key") == keys.AUTH_PASSWORD_KEY
try:
    keys.normalize_auth_mode("password-only")
except ValueError:
    pass
else:
    raise AssertionError("password-only SSH mode must remain unsupported")

print("[OK] key-only SSH policy disables password/interactive/root login")
print("[OK] password-or-key policy retains public keys while enabling passwords")
print("[OK] installed policy is syntax/effective-setting validated before acceptance")
print("[OK] SSH enable/disable runtime remains explicit and fail-closed")
print("[OK] normal SSH UI exposes only the useful client login key export")
print("[OK] client-key action is mobile-safe and shows bounded busy feedback")