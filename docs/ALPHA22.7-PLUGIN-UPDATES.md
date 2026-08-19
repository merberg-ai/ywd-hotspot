# Alpha22.7 — transactional plugin install/update

Alpha22.7 extends the uploaded `.ywdplugin` package workflow so a verified package can be installed as new source or applied as an in-place update without the manual disable → uninstall → remove-package cycle.

This build does not change MMDVM-Host, DMRGateway, duplex RF configuration, BrandMeister routing, the MMDVM voice tap, or the proven Alpha22.5 RX voice transport.

## Review first, mutate second

Package review is non-mutating. The dashboard uploads the candidate to the trusted verifier, which checks the archive format, per-file hashes, Ed25519 trust, plugin manifest, requirements, version relation, capabilities, and configuration-schema compatibility. The existing package is not replaced during review.

The review classifies a candidate as:

- `INSTALL` for a new plugin ID;
- `UPDATE` when a SemVer-compatible candidate is newer;
- `REINSTALL` for the same version;
- `DOWNGRADE` when the candidate is older;
- `REPLACE` when version ordering cannot be determined.

The modal shows current → candidate version, plugin type, signature state, requirements, configuration/data preservation, installed/enabled-state preservation, and capability additions/removals before the operator confirms anything.

## Safety boundaries

- Built-in/core plugin IDs cannot be replaced by uploaded packages.
- An uploaded plugin cannot change execution kind during an update (for example Browser UI → Service).
- Existing signer continuity is enforced. A different signing key requires an explicit remove/reinstall decision rather than silently inheriting the old package's trust.
- Capability additions are highlighted in the review UI.
- Service-plugin updates quiesce only that plugin service. Core RF/DMR services are not part of the transaction.
- Plugin data remains outside the package directory and is not touched by package replacement.
- Plugin configuration is preserved and normalized against the candidate schema. New fields receive defaults, obsolete fields are removed, and values that no longer validate are reset to the candidate field default. No plugin-supplied migration code runs as root.

## Transactional apply

`UPDATE PLUGIN` re-verifies the archive and then performs a same-filesystem staged package swap. The transaction captures the old package state, plugin enabled state, configuration, and service runtime where applicable. The candidate is validated before the old package is moved aside.

On success, the previous installed/enabled state is restored for an update. A brand-new install is registered as installed but remains disabled until explicitly enabled, matching the existing YWD plugin lifecycle.

On failure, the trusted helper restores the previous package directory, package registration state, plugin state, configuration, and service runtime before returning an error.

## First proof target

RX Monitor `0.4.0-alpha7` is intentionally the first real-world update test. With Alpha22.7 installed, leave the proven `0.4.0-alpha6.1` package installed and enabled, upload alpha7, confirm that the review shows `PLUGIN UPDATE`, then apply it without manually disabling/uninstalling/removing alpha6.1.

The RX alpha7 candidate keeps the physically proven alpha5 audio engine unchanged and advances presentation only.
