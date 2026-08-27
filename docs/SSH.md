# 🔑 SSH / SFTP Access

[← Docs index](README.md) · [Installation](INSTALL.md) · [Security](../SECURITY.md) · [Backup / Restore](BACKUP-RESTORE.md)

YWD-Hotspot OS includes OpenSSH for optional maintenance access, but the **public factory image ships with SSH disabled and TCP port 22 closed**. There is no factory password intended for SSH login.

On current development builds, the authenticated dashboard can enable SSH using either:

```text
KEY ONLY          recommended/default
PASSWORD OR KEY   explicit operator opt-in
```

Root SSH login, empty-password login, and keyboard-interactive/challenge-response authentication remain disabled in both modes.

## Factory/default security state

A freshly flashed public appliance remains:

```text
SSH                        OFF
port 22                    closed
managed login policy       key-only when first enabled
root SSH                   disabled
factory client key         none
reusable factory host key  none
```

The first time SSH is enabled, the appliance generates its own unique OpenSSH server host keys. Disabling and later re-enabling SSH preserves those server identity keys, the selected authentication policy, Linux account passwords, and existing `authorized_keys` entries.

Do not forward port 22 directly from the public Internet unless you intentionally accept that exposure. For remote administration, prefer reaching the hotspot through a VPN or other private encrypted network.

## Dashboard setup

Unlock dashboard controls and open:

```text
SYSTEM -> SSH ACCESS
```

The SSH card reports:

- server/boot state;
- port;
- active authentication policy;
- active login user;
- authorized-key count;
- Linux password state;
- eligible normal local login users.

### Login user selection

YWD offers only existing local accounts that meet all of these checks:

```text
UID                 1000 or higher
shell               interactive
home                directly under /home
root/service users  rejected
```

The normal factory appliance account is `ywd`. Development builds also allow another existing normal local account to be selected. This is useful on systems where the expected `ywd` account is absent or on source-installed systems that already have a normal operator account.

Selecting another account does **not** create, rename, repair, or delete Linux users. A missing `ywd` account is therefore still visible for later troubleshooting rather than being silently repaired by the SSH feature.

## Key-only mode — recommended

Choose:

```text
Authentication: Key only — recommended
```

Optionally create a client key before opening port 22:

```text
CREATE & EXPORT CLIENT KEY
```

YWD-Hotspot will:

1. generate a new Ed25519 client key pair;
2. add only the public key to the selected user's `~/.ssh/authorized_keys`;
3. return a `.tar.gz` containing the private/public pair and README;
4. discard its temporary copy of the private key after the response.

Then press:

```text
ENABLE SSH ACCESS
```

YWD writes and validates a managed sshd policy, generates unique host keys if needed, opens TCP port 22, and enables SSH at boot.

Key-only effective policy includes:

```text
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitEmptyPasswords no
PermitRootLogin no
AuthenticationMethods publickey
```

## Password-or-key mode

Choose:

```text
Authentication: Password or key
```

This mode accepts **either** the selected Linux user's password **or** an authorized SSH client key. It is not two-factor authentication requiring both credentials.

If you want to set/change the selected account password from YWD, enter it twice under **SSH LOGIN PASSWORD** and press:

```text
SET / CHANGE PASSWORD
```

Password rules for the dashboard helper:

```text
minimum length  10 characters
maximum length  128 characters
newline/NUL     rejected
```

The password is passed only to the local privileged password helper through stdin. It is not returned by the API, written to YWD configuration, placed in command-line arguments, or included in diagnostics.

After setting the password, enable SSH. If SSH is already running, change the authentication selector and press:

```text
APPLY AUTHENTICATION
```

The managed configuration is syntax-checked and its effective sshd settings are verified before the change is accepted. The dashboard keeps public-key authentication enabled as a recovery path.

Password-or-key effective policy includes:

```text
PubkeyAuthentication yes
PasswordAuthentication yes
KbdInteractiveAuthentication no
PermitEmptyPasswords no
PermitRootLogin no
```

## Managed login scope

The generated YWD sshd policy also includes an `AllowUsers` entry for the selected dashboard login account. Changing the selected account and applying the policy therefore changes which account YWD intends to expose through its managed SSH path.

The YWD drop-in is installed early in `sshd_config.d` and the helper checks the **effective** `sshd -T` result before accepting a policy. This prevents a conflicting distribution default from silently defeating the dashboard selection.

## Connect with a password

Linux/macOS/Windows OpenSSH:

```bash
ssh USER@HOTSPOT-IP
```

Enter the selected Linux account password when prompted.

SFTP:

```bash
sftp USER@HOTSPOT-IP
```

GUI SSH/SFTP clients use:

```text
Host      hotspot LAN IP/name
Port      22
Username  selected SSH login user
Auth      Password
Password  selected Linux account password
```

## Connect with an exported client key

Extract the downloaded archive and protect the private key:

```bash
tar -xzf *-ssh-client-login-*.tar.gz
chmod 600 ywd_hotspot_client_ed25519
ssh -i ./ywd_hotspot_client_ed25519 USER@HOTSPOT-IP
```

SFTP:

```bash
sftp -i ./ywd_hotspot_client_ed25519 USER@HOTSPOT-IP
```

Recent Windows includes `ssh` and `sftp`. If Windows OpenSSH rejects the private key because its ACL is too broad, restrict inheritance/read access before connecting.

The first connection to a newly initialized appliance normally asks you to trust its new server fingerprint. An unexpected fingerprint change later should be investigated rather than blindly accepted.

## Important administrator warning

> [!CAUTION]
> On the normal YWD-Hotspot appliance image, `ywd` has passwordless sudo for appliance administration. Password or client-key access to that account therefore grants effective administrative/root capability after login. Treat both the password and private client key as administrator credentials.

Another selected local account has whatever privileges that Linux account already possesses; YWD does not automatically grant it sudo access.

## Disable SSH

From the authenticated dashboard:

```text
SYSTEM -> SSH ACCESS -> DISABLE SSH ACCESS
```

Disabling SSH:

- closes TCP port 22;
- removes boot activation;
- preserves the selected authentication policy;
- preserves Linux account passwords;
- preserves server host keys;
- preserves client `authorized_keys` entries.

## Multiple client keys and revocation

Every **CREATE & EXPORT CLIENT KEY** action creates another independent Ed25519 key and appends its public half to the selected user's `authorized_keys` file.

To revoke a key, remove its matching line from that user's:

```text
/home/USER/.ssh/authorized_keys
```

The downloaded key archive identifies the comment used on that line. If a key may have been stolen and you cannot revoke it immediately, disable SSH from the dashboard until you can remove it.

## Server identity export is not a login key

**EXPORT SERVER IDENTITY** exports the hotspot's private `ssh_host_*` server identity keys for advanced recovery. It preserves the server fingerprint after a rebuild.

It cannot be used as a client login credential. The archive is not encrypted and contains private server keys, so store it privately.

## Backup / reflash behavior

The normal encrypted `.ywdsettings` backup does **not** currently contain:

- SSH client private keys;
- user `authorized_keys` files;
- Linux account passwords;
- OpenSSH `ssh_host_*` identity keys.

After a fresh public-image flash, SSH is off again. Configure SSH from the dashboard on the replacement system.

## Troubleshooting

Useful local-console checks:

```bash
getent passwd ywd
getent passwd | awk -F: '$3 >= 1000 && $3 < 65534 {print $1,$3,$6,$7}'
systemctl status ssh.service --no-pager
sudo ss -ltnp | grep ':22 ' || true
sudo sshd -t
sudo sshd -T | grep -E '^(pubkeyauthentication|passwordauthentication|kbdinteractiveauthentication|permitrootlogin|authenticationmethods|allowusers) '
ls -la /etc/ssh/sshd_config.d/
```

Common causes of connection failure:

- SSH access is still disabled;
- wrong LAN IP/hostname;
- wrong selected login user;
- selected Linux user no longer exists;
- password was not set/known for password mode;
- client did not select the exported private key;
- private-key file permissions rejected by the client;
- stale/mismatched server fingerprint after a reflash;
- OpenSSH server missing on a generic source-installed OS.

The normal sanitized YWD diagnostics bundle is preferred for support. Never attach passwords, client private keys, server identity archives, raw `/etc/shadow`, or raw `authorized_keys` data to a public issue.
