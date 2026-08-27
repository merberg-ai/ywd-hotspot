#!/usr/bin/env python3
"""Update local DMR identity files from the existing RadioID.net CSV feed."""
import csv
import io
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

URL = os.environ.get("YWD_DMRID_URL", "https://database.radioid.net/static/user.csv")
OUT = Path(os.environ.get("YWD_DMRID_FILE", "/var/lib/ywd-hotspot/DMRIds.dat"))
RICH_OUT = Path(os.environ.get("YWD_DMR_CONTACTS_FILE", "/var/lib/ywd-hotspot/DMRContacts.tsv"))
INDEX_OUT = Path(os.environ.get("YWD_DMR_CONTACTS_DB", "/var/lib/ywd-hotspot/DMRContacts.sqlite3"))
CFG = Path(os.environ.get("YWD_CONFIG", "/etc/ywd-hotspot/config.json"))
UA = "YWD-Hotspot/0.2.0"


def interval_days():
    try:
        c = json.loads(CFG.read_text())
        return max(1, min(30, int(c.get("maintenance", {}).get("dmrid_update_days", 7))))
    except Exception:
        return 7


def due():
    if not OUT.is_file() or not RICH_OUT.is_file() or not INDEX_OUT.is_file():
        return True
    try:
        age = time.time() - min(OUT.stat().st_mtime, RICH_OUT.stat().st_mtime, INDEX_OUT.stat().st_mtime)
    except FileNotFoundError:
        return True
    return age >= interval_days() * 86400


def _clean(value, limit=80):
    text = " ".join(str(value or "").replace("\t", " ").replace("\r", " ").replace("\n", " ").split())
    return text[:limit]


def _header_map(row):
    normalized = [re.sub(r"[^a-z0-9]", "", str(value or "").lower()) for value in row]
    names = set(normalized)
    if not ({"radioid", "id"} & names) or "callsign" not in names:
        return None
    aliases = {
        "id": ("radioid", "id"),
        "callsign": ("callsign",),
        "name": ("name", "fullname"),
        "first": ("firstname", "first"),
        "last": ("lastname", "last"),
        "city": ("city",),
        "state": ("state", "province", "region"),
        "country": ("country",),
    }
    out = {}
    for key, choices in aliases.items():
        for choice in choices:
            if choice in normalized:
                out[key] = normalized.index(choice)
                break
    return out


def _field(row, index):
    if index is None or index < 0 or index >= len(row):
        return ""
    return row[index]


def _set_owner_mode(path):
    os.chmod(path, 0o640)
    try:
        import grp
        os.chown(path, 0, grp.getgrnam("ywd-hotspot").gr_gid)
    except Exception:
        pass


def _write_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    _set_owner_mode(tmp)
    os.replace(tmp, path)


def _write_index_atomic(rows):
    """Build the indexed rich directory off to the side, then atomically replace it."""
    INDEX_OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = INDEX_OUT.with_name(INDEX_OUT.name + ".tmp")
    try:
        tmp.unlink()
    except FileNotFoundError:
        pass
    conn = sqlite3.connect(tmp)
    try:
        conn.execute("PRAGMA journal_mode=OFF")
        conn.execute("PRAGMA synchronous=OFF")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute(
            "CREATE TABLE contacts ("
            "dmr_id INTEGER PRIMARY KEY, callsign TEXT NOT NULL, name TEXT, city TEXT, state TEXT, country TEXT)"
        )
        conn.executemany(
            "INSERT OR REPLACE INTO contacts (dmr_id, callsign, name, city, state, country) VALUES (?, ?, ?, ?, ?, ?)",
            (
                (int(parts[0]), parts[1], parts[2], parts[3], parts[4], parts[5])
                for line in rows
                for parts in [line.split("\t", 5)]
                if len(parts) == 6 and parts[0].isdigit()
            ),
        )
        conn.execute("CREATE INDEX contacts_callsign ON contacts(callsign)")
        conn.execute("PRAGMA optimize")
        conn.commit()
    finally:
        conn.close()
    _set_owner_mode(tmp)
    os.replace(tmp, INDEX_OUT)


def main():
    if os.geteuid() != 0:
        raise SystemExit("Run with sudo/root.")
    force = "--force" in sys.argv[1:]
    if not force and not due():
        print(f"DMR ID database is not due yet (configured every {interval_days()} days).")
        return

    req = urllib.request.Request(URL, headers={"User-Agent": UA, "Accept": "text/csv,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            raw = response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SystemExit(f"DMR ID update failed: {exc}")

    reader = csv.reader(io.StringIO(raw.decode("utf-8-sig", "replace")))
    simple_rows = []
    rich_rows = []
    mapping = None
    first_data = True

    for row in reader:
        if not row:
            continue
        if first_data:
            detected = _header_map(row)
            first_data = False
            if detected is not None:
                mapping = detected
                continue

        if mapping is None:
            # RadioID's long-standing static user.csv layout begins with:
            # ID, callsign, first name, last name, city, state, country.
            indexes = {"id": 0, "callsign": 1, "first": 2, "last": 3, "city": 4, "state": 5, "country": 6}
        else:
            indexes = mapping

        rid = _clean(_field(row, indexes.get("id")), 16)
        call = _clean(_field(row, indexes.get("callsign")), 24).upper()
        if not rid.isdigit() or not call:
            continue
        ident = int(rid)
        if not (1 <= ident <= 16_777_215):
            continue

        name = _clean(_field(row, indexes.get("name")), 80)
        if not name:
            first = _clean(_field(row, indexes.get("first")), 40)
            last = _clean(_field(row, indexes.get("last")), 40)
            name = _clean(f"{first} {last}", 80)
        city = _clean(_field(row, indexes.get("city")), 64)
        state = _clean(_field(row, indexes.get("state")), 48)
        country = _clean(_field(row, indexes.get("country")), 48)

        simple_rows.append(f"{ident}\t{call}")
        rich_rows.append("\t".join((str(ident), call, name, city, state, country)))

    if len(simple_rows) < 1000:
        raise SystemExit(f"DMR ID update rejected: only {len(simple_rows)} valid rows")

    _write_atomic(OUT, "\n".join(simple_rows) + "\n")
    _write_atomic(RICH_OUT, "\n".join(rich_rows) + "\n")
    _write_index_atomic(rich_rows)
    print(f"Updated {OUT}: {len(simple_rows)} DMR IDs")
    print(f"Updated {RICH_OUT}: {len(rich_rows)} local contact records")
    print(f"Updated {INDEX_OUT}: indexed DMR contact directory")


if __name__ == "__main__":
    main()
