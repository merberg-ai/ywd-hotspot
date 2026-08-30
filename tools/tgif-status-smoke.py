#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "lib"
sys.path.insert(0, str(LIB))

import dashboard_tgif


def main() -> int:
    lines = [
        "BM_3103, Opening DMR Network",
        "TGIF_Network, Opening DMR Network",
        "BM_3103, Logged into the master successfully",
        "TGIF_Network, Logged into the master successfully",
    ]
    bm = dashboard_tgif._network_state_from_lines(lines, "BM_3103", True, True)
    tg = dashboard_tgif._network_state_from_lines(lines, "TGIF_Network", True, True)
    assert bm[0] == "connected", bm
    assert tg[0] == "connected", tg

    failed = lines + ["TGIF_Network, Failed login: authentication rejected"]
    tg_failed = dashboard_tgif._network_state_from_lines(failed, "TGIF_Network", True, True)
    bm_still = dashboard_tgif._network_state_from_lines(failed, "BM_3103", True, True)
    assert tg_failed[0] == "auth-failed", tg_failed
    assert bm_still[0] == "connected", bm_still
    assert dashboard_tgif._network_state_from_lines(lines, "TGIF_Network", False, True)[0] == "disabled"
    assert dashboard_tgif._network_state_from_lines(lines, "TGIF_Network", True, False)[0] == "offline"

    activity = {
        "current": {
            "destination": {"id": 5_009_990, "display": "5009990", "group": True}
        },
        "lastheard": [
            {"destination": {"id": 9_990, "display": "9990", "group": True}},
            {"destination": {"id": 5_009_990, "display": "5009990", "group": True}},
        ],
    }
    dashboard_tgif.annotate_activity(activity)
    current = activity["current"]["destination"]
    assert current["network"] == "tgif", current
    assert current["network_id"] == 9990, current
    assert current["rf_id"] == 5009990, current
    assert current["label"] == "TGIF · TG 9990 · Parrot", current

    bm_dst = activity["lastheard"][0]["destination"]
    assert bm_dst["network"] == "brandmeister", bm_dst
    assert bm_dst["network_id"] == 9990, bm_dst
    assert bm_dst["label"] == "BM · TG 9990 · Parrot", bm_dst

    print("TGIF dashboard status smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
