# 🎨 Branding Assets

[← Project README](../../README.md)

This directory holds the canonical YWD-Hotspot source artwork and lightweight derivatives used by GitHub, the WebUI, and image builds.

| Asset | Purpose |
|---|---|
| `ywd-hotspot-logo-master.png` | original high-resolution source artwork |
| `ywd-hotspot-badge-256.webp` | lightweight square badge used by repository/runtime UI surfaces |
| `ywd-hotspot-banner-webui.webp` | optimized wide hero/banner derivative for the WebUI and repository front door |

The dashboard runtime also carries:

```text
web/ywd-hotspot-banner.webp
```

That WebUI copy is intentional: `web/` is atomically deployed by normal application updates, so the hero asset can update with the browser payload without serving a multi-megabyte source image on the Pi Zero.

## Rules when changing branding

- preserve the master/source artwork rather than repeatedly recompressing an old derivative
- generate small WebP derivatives appropriate to their actual display size
- visually decode/inspect generated WebP files before committing them
- verify the WebP RIFF declared length matches the actual file length
- keep the source branding derivative and runtime `web/` copy synchronized when they represent the same artwork
- bump the WebUI cache key when replacing a runtime image
- never serve the multi-megabyte master PNG from the hotspot dashboard

The original Pi Zero W remains the storage/memory/network performance budget, so small validated derivatives are preferred over oversized assets.
