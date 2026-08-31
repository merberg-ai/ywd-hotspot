#!/usr/bin/env python3
"""Offline smoke checks for TGIF directory normalization/search semantics."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "lib"
sys.path.insert(0, str(LIB))

spec = importlib.util.spec_from_file_location("dashboard_tgif_smoke", LIB / "dashboard_tgif.py")
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def main() -> int:
    # Deliberately omit TGIF Parrot from the remote payload. The real public
    # export does not necessarily contain service destinations such as Parrot,
    # so YWD must merge its proven known-TG metadata locally.
    rows = mod.normalize_tgif_talkgroups([
        {"id": "31665", "name": "TGIF Network"},
        {"id": 171, "name": "DX WORLD-WIDE", "country": "US", "language": "English"},
        {"id": 1234567, "name": "Legacy seven digit"},
        {"id": "bad", "name": "ignore me"},
    ])
    by_id = {row["id"]: row for row in rows}

    assert by_id[9990]["name"] == "Parrot"
    assert by_id[9990]["synthetic"] is True
    assert by_id[9990]["supported"] is True
    assert by_id[9990]["rf_talkgroup"] == 5_009_990
    assert by_id[31665]["rf_talkgroup"] == 5_031_665
    assert by_id[171]["rf_talkgroup"] == 5_000_171
    assert by_id[1234567]["supported"] is False
    assert by_id[1234567]["rf_talkgroup"] is None
    assert len(rows) == 4

    original = mod.tgif_directory
    mod.tgif_directory = lambda force=False: (rows, 123.0, False, None)
    try:
        result = mod.search_tgif_talkgroups(query="world", limit=50)
        assert [row["id"] for row in result["results"]] == [171]

        result = mod.search_tgif_talkgroups(query="9990", limit=50)
        assert result["results"][0]["id"] == 9990
        assert result["results"][0]["name"] == "Parrot"
        assert result["results"][0]["rf_talkgroup"] == 5_009_990

        result = mod.search_tgif_talkgroups(query="31665", limit=50)
        assert result["results"][0]["id"] == 31665
        assert result["results"][0]["rf_talkgroup"] == 5_031_665

        # Exact numeric search must remain usable even when the remote catalog
        # has no metadata row for the requested valid TGIF talkgroup.
        result = mod.search_tgif_talkgroups(query="424242", limit=50)
        assert result["results"][0]["id"] == 424242
        assert result["results"][0]["name"] == "TG 424242"
        assert result["results"][0]["synthetic"] is True
        assert result["results"][0]["supported"] is True
        assert result["results"][0]["rf_talkgroup"] == 5_424_242

        result = mod.search_tgif_talkgroups(ids=[9990, 31665, 424242], limit=50)
        assert [row["id"] for row in result["results"]] == [9990, 31665, 424242]
        assert result["results"][2]["synthetic"] is True
        assert result["rf_base"] == 5_000_000
        assert result["rf_max_network_tg"] == 999_999
    finally:
        mod.tgif_directory = original

    print("TGIF directory smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
