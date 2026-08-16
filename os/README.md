# YWD-Hotspot OS

This directory contains the experimental image-building infrastructure for YWD-Hotspot OS.

## Safety boundary

The normal YWD-Hotspot install and update paths do not depend on anything under `os/`.

- `main` remains the stable application branch.
- `dev` remains normal application development.
- `dev-os` is the isolated OS/image-development branch.

OS work should consume the current application from this repository, but OS-only changes must not be merged back into `dev` wholesale. Reusable application changes should be moved back deliberately as focused commits or pull requests.

## Initial target

The first target is Raspberry Pi Zero W / Zero WH (`armhf`) using a Raspberry Pi OS Lite base. The initial milestone is intentionally boring: reproducibly build a vanilla bootable image on a faster builder host before layering YWD-Hotspot into it.

## Layout

- `builder/` — host-side build, doctor, and clean scripts.
- `pi-gen/` — pinned upstream pi-gen metadata and future custom stages.
- `overlay/` — files copied into the target root filesystem in later milestones.
- `firstboot/` — first-boot service and provisioning logic in later milestones.
- `network/` — setup/recovery AP logic in later milestones.
- `provisioning/` — provisioning schema and helpers in later milestones.
- `docs/` — OS-specific design and build notes.

Generated images, build work directories, caches, and deploy artifacts are intentionally excluded from Git.
