# 🔑 SSH / SFTP Access

[← Docs index](README.md) · [Installation](INSTALL.md) · [Security](../SECURITY.md) · [Backup / Restore](BACKUP-RESTORE.md)

YWD-Hotspot OS includes OpenSSH for optional maintenance access, but the **public factory image ships with SSH disabled and TCP port 22 closed**. There is no default SSH password to discover or enable.

The supported YWD-Hotspot OS workflow is dashboard-managed, public-key-only access:

```text
factory image
  -> SSH OFF / port 22 closed
  -> unlock dashboard controls
  -> SYSTEM -> SSH ACCESS
  -> create + download a client login key
  -> enable SSH access
  -> ssh/sftp with that private key
```

## Security model

Whenever YWD enables SSH it enforces:

```text
port                       22
public-key authentication  enabled
password authentication    disabled
keyboard-interactive auth  disabled
root SSH login             disabled
factory host keys           none
```

The first time SSH is enabled, the appliance generates its own unique OpenSSH server host keys. Disabling and later re-enabling SSH preserves those server identity keys and existing `authorized_keys` entries.

> [!CAUTION]
> On the YWD-Hotspot OS image, the normal `ywd` account has passwordless sudo for appliance administration. A client private key authorized for `ywd` therefore grants effective administrative/root capability. Treat that private key like an administrator credential.

Do not forward port 22 directly from the public Internet unless you intentionally accept that exposure. For remote administration, prefer reaching the hotspot through a VPN or other private encrypted network and then use SSH normally.

## Recommended setup on the public appliance image

### 1. Unlock dashboard controls

Open the normal YWD-Hotspot dashboard on the trusted LAN and unlock controls with the dashboard password created during first-boot setup.

### 2. Open the SSH card

Go to:

```text
SYSTEM -> SSH ACCESS
```

The card shows the current server state, boot state, port, authentication policy, login-user hint, and authorized-key count.

### 3. Create the client login key before opening SSH

The public appliance uses the normal Linux user:

```text
ywd
```

Leave `ywd` in the **SSH / SFTP CLIENT LOGIN KEY** field and press:

```text
CREATE & EXPORT CLIENT KEY
```

YWD-Hotspot will:

1. generate a new Ed25519 client key pair;
2. add only the public key to `/home/ywd/.ssh/authorized_keys`;
3. return a `.tar.gz` archive containing the private/public client key pair and a README;
4. discard its temporary copy of the private key after the response.

The archive name contains the current hotspot hostname, selected username and creation timestamp, for example:

```text
ywd-hotspot-ywd-ssh-client-login-20260822-070000.tar.gz
```

The private key is generated **without a passphrase** so it can be imported by common SSH/SFTP clients. Store it accordingly. Anyone who obtains it can authenticate while the matching public key remains authorized.

Creating a key does **not** open port 22, so creating/downloading the key first is the preferred order.

### 4. Enable SSH

Press:

```text
ENABLE SSH ACCESS
```

Confirm the dialog. YWD creates unique server host keys if they do not already exist, installs the YWD public-key-only sshd policy, opens TCP port 22, and enables SSH at boot.

The card should report:

```text
Server   RUNNING
At boot  ENABLED
Port     22
Policy   PUBLIC KEY ONLY
```

## Connect from Linux or macOS

Extract the downloaded archive, protect the private key, and connect:

```bash
tar -xzf *-ywd-ssh-client-login-*.tar.gz
chmod 600 ywd_hotspot_client_ed25519
ssh -i ./ywd_hotspot_client_ed25519 ywd@HOTSPOT-IP
```

SFTP:

```bash
sftp -i ./ywd_hotspot_client_ed25519 ywd@HOTSPOT-IP
```

Replace `HOTSPOT-IP` with the LAN address shown by the hotspot/dashboard. `ywd-hotspot.local` may also work when the client network supports mDNS:

```bash
ssh -i ./ywd_hotspot_client_ed25519 ywd@ywd-hotspot.local
```

The first connection to a newly initialized appliance normally asks you to trust its new server fingerprint. A later unexpected fingerprint change should be investigated rather than blindly accepted.

## Connect from Windows 10/11 OpenSSH

Recent Windows includes the `ssh` and `sftp` clients. In PowerShell, extract the archive and place the private key somewhere private, for example under your user `.ssh` directory:

```powershell
tar -xzf .\*-ywd-ssh-client-login-*.tar.gz
New-Item -ItemType Directory -Force "$env:USERPROFILE\.ssh" | Out-Null
Move-Item .\ywd_hotspot_client_ed25519 "$env:USERPROFILE\.ssh\ywd_hotspot_client_ed25519"
ssh -i "$env:USERPROFILE\.ssh\ywd_hotspot_client_ed25519" ywd@HOTSPOT-IP
```

SFTP:

```powershell
sftp -i "$env:USERPROFILE\.ssh\ywd_hotspot_client_ed25519" ywd@HOTSPOT-IP
```

If Windows OpenSSH rejects the private key because its ACL is too broad, restrict inheritance and grant your account read access:

```powershell
$key = "$env:USERPROFILE\.ssh\ywd_hotspot_client_ed25519"
icacls $key /inheritance:r
icacls $key /grant:r "${env:USERNAME}:(R)"
```

GUI SSH/SFTP clients may either accept the OpenSSH Ed25519 private key directly or require importing/converting it with that client's key utility. Use:

```text
Host      hotspot LAN IP/name
Port      22
Username  ywd
Auth      downloaded private client key
Password  none
```

## Source-installed / non-appliance systems

A normal GitHub source install does not create the YWD appliance `ywd` login account or install OpenSSH on behalf of an existing general-purpose OS. The SSH dashboard helper can enroll a key only for an existing normal local account that:

- has UID 1000 or higher;
- has an interactive shell;
- has a home directory directly under `/home`.

If you installed YWD-Hotspot onto an existing Pi, enter that existing username in the client-key field instead of `ywd`. OpenSSH server must already be installed for the dashboard enable action to work.

## Disable SSH

From the authenticated dashboard:

```text
SYSTEM -> SSH ACCESS -> DISABLE SSH ACCESS
```

Disabling SSH:

- closes TCP port 22;
- removes boot activation;
- preserves server host keys;
- preserves client `authorized_keys` entries.

Re-enabling SSH later therefore restores access with the same still-authorized client keys and normally the same server fingerprint.

## Multiple client keys and revocation

Every **CREATE & EXPORT CLIENT KEY** action creates another independent Ed25519 key and appends its public half to the selected user's `authorized_keys` file.

There is currently no dashboard button that selectively deletes an individual authorized client key. To revoke one permanently, remove its line from:

```text
/home/ywd/.ssh/authorized_keys
```

The downloaded key archive identifies the comment used on that line. If a client key may have been stolen and you cannot immediately edit `authorized_keys`, disable SSH from the dashboard to close port 22 until you can revoke it.

## Server identity export is not a login key

The SSH card also offers:

```text
EXPORT SERVER IDENTITY
```

This is **recovery-only**. It exports the hotspot's private `ssh_host_*` server identity keys so an advanced rebuild can preserve the same SSH server fingerprint.

It cannot be used by SSH, PuTTY, WinSCP, andFTP, or another client as a login credential.

The server-identity archive is not encrypted and contains private server keys. Possession can allow impersonation of that SSH server, so store it privately.

## Backup / reflash behavior

The normal encrypted `.ywdsettings` backup does **not** currently contain:

- SSH client private keys;
- `/home/ywd/.ssh/authorized_keys`;
- OpenSSH server `ssh_host_*` identity keys.

After a fresh public-image flash, SSH is off again. The simplest recovery path is to create a new client login key and then enable SSH. If preserving the old server fingerprint matters, use the separate **EXPORT SERVER IDENTITY** recovery archive and restore it manually as root.

## Troubleshooting

From an existing shell/console, useful checks are:

```bash
systemctl status ssh.service --no-pager
sudo ss -ltnp | grep ':22 ' || true
sudo sshd -t
sudo sshd -T | grep -E '^(pubkeyauthentication|passwordauthentication|kbdinteractiveauthentication|permitrootlogin|authenticationmethods) '
ls -ld /home/ywd/.ssh
ls -l /home/ywd/.ssh/authorized_keys
```

Expected YWD policy includes public-key authentication, password authentication off, and root login off.

Common causes of connection failure:

- SSH Access still disabled in the dashboard;
- wrong LAN IP/hostname;
- client did not select the downloaded private key;
- wrong username;
- private-key file permissions rejected by the client;
- client key was created for a different local Linux user;
- stale/mismatched server fingerprint after a reflash;
- OpenSSH server missing on a generic source-installed OS.

The normal sanitized YWD diagnostics bundle is preferred for support. Never attach client private keys, server identity archives, or raw `authorized_keys` data to a public issue.
