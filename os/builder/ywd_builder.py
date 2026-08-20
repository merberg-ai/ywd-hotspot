#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Footer, Header, Input, Label, RichLog, Static, TabbedContent, TabPane

from profile_model import PROFILE_PATH, compile_profile, default_profile, get_path, load_profile, save_profile, set_path

ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "os" / "builder"


@dataclass(frozen=True)
class Field:
    path: str
    label: str
    kind: str = "str"
    help: str = ""
    secret: bool = False


SECTIONS: list[tuple[str, str, list[Field]]] = [
    ("image", "IMAGE + WI-FI", [
        Field("image.image_name", "Image name", help="Output image basename."),
        Field("image.os_version", "OS identity", help="Build label shown in console/About metadata."),
        Field("wifi.ssid", "Wi-Fi SSID", help="Blank = use setup AP on first boot."),
        Field("wifi.password", "Wi-Fi password", secret=True, help="Blank is valid for an open network."),
        Field("wifi.hidden", "Hidden Wi-Fi", "bool", help="yes/no"),
    ]),
    ("station", "STATION", [
        Field("config.station.callsign", "Callsign", help="Blank = first-boot wizard required."),
        Field("config.station.base_dmr_id", "Base DMR ID", help="Blank = first-boot wizard required."),
        Field("config.station.essid", "ESSID", help="01-99, or blank for no suffix."),
        Field("config.station.location", "Location"),
        Field("config.station.description", "Description"),
        Field("config.station.latitude", "Latitude", "float"),
        Field("config.station.longitude", "Longitude", "float"),
        Field("config.station.height", "Antenna height (m)", "int"),
        Field("config.station.url", "Station URL"),
    ]),
    ("radio", "MMDVM / RF", [
        Field("config.radio.mode", "HAT mode", "choice", "simplex | duplex"),
        Field("config.radio.frequency_hz", "Simplex frequency (Hz)", "int"),
        Field("config.radio.rx_frequency_hz", "Duplex hotspot RX (Hz)", "int"),
        Field("config.radio.tx_frequency_hz", "Duplex hotspot TX (Hz)", "int"),
        Field("config.radio.color_code", "Color code", "int"),
        Field("config.radio.rx_offset", "RX offset (Hz)", "int"),
        Field("config.radio.tx_offset", "TX offset (Hz)", "int"),
        Field("config.radio.tx_invert", "TX invert", "int", "0 or 1"),
        Field("config.radio.rx_invert", "RX invert", "int", "0 or 1"),
        Field("config.radio.rx_level", "RX level", "int", "0-100"),
        Field("config.radio.tx_level", "TX level", "int", "0-100"),
        Field("config.radio.rf_level", "RF level", "int", "0-100"),
        Field("config.radio.jitter_ms", "DMR jitter (ms)", "int"),
        Field("config.radio.call_hang_s", "Call hang (s)", "int"),
        Field("config.radio.tx_hang_s", "TX hang (s)", "int"),
        Field("config.radio.timeout_s", "RF timeout (s)", "int"),
        Field("config.radio.uart", "MMDVM UART"),
        Field("config.radio.uart_speed", "UART speed", "int"),
    ]),
    ("bm", "BRANDMEISTER + SECURITY", [
        Field("config.brandmeister.enabled", "BrandMeister enabled", "bool", "yes/no"),
        Field("config.brandmeister.master", "BrandMeister master"),
        Field("config.brandmeister.port", "BrandMeister port", "int"),
        Field("credentials.hotspot_password", "Hotspot Security password", secret=True, help="Required to skip setup when BM is enabled."),
        Field("credentials.bm_api_key", "BrandMeister API key", secret=True, help="Optional; enables dashboard TG controls."),
        Field("credentials.dashboard_password", "Dashboard control password", secret=True, help="8+ chars required to skip setup wizard."),
    ]),
    ("display", "OLED DISPLAY", [
        Field("config.display.enabled", "OLED enabled", "bool"),
        Field("config.display.i2c_bus", "I2C bus", "int"),
        Field("config.display.address", "I2C address"),
        Field("config.display.brightness", "Brightness", "int", "1-255"),
        Field("config.display.idle_timeout_s", "Idle timeout (s)", "int"),
        Field("config.display.rotation", "Rotation", "int", "0 or 180"),
        Field("config.display.runtime_mode", "Runtime mode", "choice", "basic | enhanced | minimal"),
        Field("config.display.large_callsign", "Large callsign", "bool"),
        Field("config.display.callsign_size", "Callsign size", "choice", "auto | normal | large | huge"),
        Field("config.display.show_talkgroup", "Show talkgroup", "bool"),
        Field("config.display.talkgroup_format", "Talkgroup format", "choice", "number | name | name_number"),
        Field("config.display.show_slot", "Show slot", "bool"),
        Field("config.display.show_elapsed", "Show elapsed", "bool"),
        Field("config.display.show_ber", "Show BER", "bool"),
        Field("config.display.show_rssi", "Show RSSI", "bool"),
        Field("config.display.show_loss", "Show packet loss", "bool"),
        Field("config.display.post_call_hold_s", "Post-call hold (s)", "int"),
        Field("config.display.idle_cycle", "Idle page cycle", "bool"),
        Field("config.display.idle_cycle_s", "Idle cycle interval (s)", "int"),
    ]),
    ("meters", "INSTRUMENTATION", [
        Field("config.display.instrumentation.enabled", "Instrumentation enabled", "bool"),
        Field("config.display.instrumentation.preset", "Preset", "choice", "basic | balanced | instrument | maximum | custom"),
        Field("config.display.instrumentation.signal_meter", "Signal meter", "bool"),
        Field("config.display.instrumentation.signal_style", "Signal style", "choice", "segmented | smooth"),
        Field("config.display.instrumentation.signal_segments", "Signal segments", "int"),
        Field("config.display.instrumentation.rssi_min_dbm", "RSSI minimum (dBm)", "int"),
        Field("config.display.instrumentation.rssi_max_dbm", "RSSI maximum (dBm)", "int"),
        Field("config.display.instrumentation.peak_hold", "Peak hold", "bool"),
        Field("config.display.instrumentation.peak_hold_ms", "Peak hold (ms)", "int"),
        Field("config.display.instrumentation.quality_meter", "Quality meter", "bool"),
        Field("config.display.instrumentation.ber_excellent", "BER excellent (%)", "float"),
        Field("config.display.instrumentation.ber_good", "BER good (%)", "float"),
        Field("config.display.instrumentation.ber_fair", "BER fair (%)", "float"),
        Field("config.display.instrumentation.tx_meter", "TX meter", "bool"),
        Field("config.display.instrumentation.measurement_hold_s", "Measurement hold (s)", "int"),
        Field("config.display.instrumentation.history_rssi", "RSSI history", "bool"),
        Field("config.display.instrumentation.history_ber", "BER history", "bool"),
        Field("config.display.instrumentation.history_mode", "History mode", "choice", "samples | time"),
        Field("config.display.instrumentation.history_samples", "History samples", "int"),
        Field("config.display.instrumentation.history_max_age_s", "History max age (s)", "int"),
        Field("config.display.instrumentation.history_seconds", "History seconds", "int"),
        Field("config.display.instrumentation.render_fps", "Render FPS", "int", "5 | 10 | 20"),
        Field("config.display.instrumentation.animation", "Animation", "choice", "off | subtle | normal | high"),
        Field("config.display.instrumentation.idle_animation", "Idle animation", "bool"),
        Field("config.display.instrumentation.live_status_strip", "Live status strip", "bool"),
        Field("config.display.instrumentation.show_numeric_values", "Show numeric values", "bool"),
        Field("config.display.instrumentation.meter_labels", "Meter labels", "choice", "compact | full"),
        Field("config.display.instrumentation.reduced_motion", "Reduced motion", "choice", "system | reduce | full"),
    ]),
    ("maintenance", "WEB + MAINTENANCE", [
        Field("config.web.bind", "Dashboard bind address"),
        Field("config.web.port", "Dashboard port", "int"),
        Field("config.maintenance.rf_autostart", "Enable RF on first boot", "bool", "Default no; explicit opt-in."),
        Field("config.maintenance.persistent_journal", "Persistent journal", "bool"),
        Field("config.maintenance.journal_max_mb", "Journal maximum (MB)", "int"),
        Field("config.maintenance.dmrid_update_days", "DMR ID update interval (days)", "int"),
        Field("config.maintenance.config_history_keep", "Config history snapshots", "int"),
    ]),
]

FIELDS = [field for _, _, fields in SECTIONS for field in fields]
FIELD_BY_ID = {"f_" + field.path.replace(".", "_"): field for field in FIELDS}


def display_value(field: Field, value: Any) -> str:
    if field.kind == "bool":
        return "yes" if bool(value) else "no"
    return "" if value is None else str(value)


def parse_value(field: Field, text: str, fallback: Any) -> Any:
    s = text.strip()
    if field.kind == "bool":
        if not s:
            return bool(fallback)
        low = s.lower()
        if low in {"1", "true", "yes", "y", "on", "enabled"}:
            return True
        if low in {"0", "false", "no", "n", "off", "disabled"}:
            return False
        raise ValueError(f"{field.label}: use yes or no")
    if field.kind == "int":
        return fallback if not s else int(s)
    if field.kind == "float":
        return fallback if not s else float(s)
    return text.strip()


class BuilderApp(App):
    TITLE = "YWD-Hotspot OS Builder"
    SUB_TITLE = "dev-builder · interactive appliance image forge"

    CSS = """
    Screen { background: #070d12; color: #eaf8ff; }
    Header { background: #08151e; color: #45dcff; }
    Footer { background: #08151e; color: #8da7b7; }
    #hero { height: 7; border: round #254258; background: #0b1720; margin: 1 2 0 2; padding: 1 2; }
    #hero-title { color: #45dcff; text-style: bold; }
    #hero-sub { color: #8c8cff; }
    #readiness { margin-top: 1; color: #8da7b7; }
    TabbedContent { margin: 1 2; }
    TabPane { background: #0a141c; padding: 1; }
    .form { height: 1fr; padding: 0 1 1 1; }
    .section-title { color: #45dcff; text-style: bold; margin: 1 0; }
    .field-row { height: auto; min-height: 5; border-bottom: solid #17333d; padding: 0 1 1 1; }
    .field-label { color: #d9f5ff; text-style: bold; }
    .field-help { color: #7792a3; }
    Input { background: #07131b; border: tall #31546d; color: #eaf8ff; }
    Input:focus { border: tall #45dcff; }
    #build-actions { height: auto; margin: 1 0; }
    Button { margin-right: 1; }
    Button.-primary { background: #45dcff; color: #061118; }
    #build-log { height: 1fr; min-height: 18; border: round #254258; background: #050b10; }
    """

    BINDINGS = [
        ("ctrl+s", "save_profile", "Save profile"),
        ("ctrl+v", "validate_profile", "Validate"),
        ("ctrl+d", "run_doctor", "Doctor"),
        ("ctrl+b", "run_build", "Build"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.profile = load_profile()
        self.defaults = default_profile()
        self.task_running = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="hero"):
            yield Static("YWD // HOTSPOT OS BUILDER", id="hero-title")
            yield Static("Interactive preconfiguration · Pi Zero W / MMDVM · RF-safe by default", id="hero-sub")
            yield Static("Checking profile…", id="readiness")
        with TabbedContent(initial="image"):
            for tab_id, title, fields in SECTIONS:
                with TabPane(title, id=tab_id):
                    with VerticalScroll(classes="form"):
                        yield Static(title, classes="section-title")
                        for field in fields:
                            fid = "f_" + field.path.replace(".", "_")
                            with Vertical(classes="field-row"):
                                yield Label(field.label, classes="field-label")
                                if field.help:
                                    yield Static(field.help, classes="field-help")
                                yield Input(value=display_value(field, get_path(self.profile, field.path, "")), id=fid, password=field.secret)
            with TabPane("BUILD", id="build"):
                with Vertical():
                    yield Static("BUILD CONTROL", classes="section-title")
                    yield Static("Save/validate the profile, run builder doctor, then build. The build uses temporary ignored overlays; secrets remain under os/local and are never committed.", classes="field-help")
                    with Horizontal(id="build-actions"):
                        yield Button("SAVE PROFILE", id="save", variant="primary")
                        yield Button("VALIDATE", id="validate")
                        yield Button("DOCTOR", id="doctor")
                        yield Button("BUILD IMAGE", id="build-image", variant="success")
                    yield RichLog(id="build-log", wrap=True, highlight=True, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_readiness()
        self.query_one("#build-log", RichLog).write(f"Profile: {PROFILE_PATH}")

    def collect_profile(self) -> dict[str, Any]:
        profile = load_profile()
        defaults = default_profile()
        for fid, field in FIELD_BY_ID.items():
            widget = self.query_one("#" + fid, Input)
            fallback = get_path(defaults, field.path, "")
            value = parse_value(field, widget.value, fallback)
            set_path(profile, field.path, value)
        return profile

    def save_current(self) -> dict[str, Any]:
        profile = self.collect_profile()
        save_profile(profile)
        self.profile = profile
        return profile

    def refresh_readiness(self) -> None:
        node = self.query_one("#readiness", Static)
        try:
            compiled = compile_profile(self.collect_profile())
            if compiled["complete"]:
                wifi = "Wi-Fi preseeded" if compiled["wifi"]["ssid"] else "Wi-Fi via setup AP"
                node.update(f"[bold #78f0b0]FULLY PRECONFIGURED[/] · hotspot wizard skipped · {wifi} · RF {'ON' if compiled['config']['maintenance']['rf_autostart'] else 'OFF'}")
            else:
                node.update("[bold #ffd76a]FIRST-BOOT WIZARD REQUIRED[/] · deferred: " + ", ".join(compiled["missing"]))
        except Exception as exc:
            node.update(f"[bold #ff7282]PROFILE ERROR[/] · {exc}")

    def action_save_profile(self) -> None:
        self.do_save()

    def action_validate_profile(self) -> None:
        self.do_validate()

    def action_run_doctor(self) -> None:
        self.do_task(["bash", str(BUILDER / "DOCTOR.sh")], "BUILDER DOCTOR")

    def action_run_build(self) -> None:
        self.do_save()
        self.do_task(["bash", str(BUILDER / "RUN-BUILD.sh")], "IMAGE BUILD")

    def do_save(self) -> None:
        log = self.query_one("#build-log", RichLog)
        try:
            self.save_current()
            self.refresh_readiness()
            log.write("[green]Profile saved.[/green]")
        except Exception as exc:
            log.write(f"[red]Save failed: {exc}[/red]")

    def do_validate(self) -> None:
        log = self.query_one("#build-log", RichLog)
        try:
            profile = self.save_current()
            compiled = compile_profile(profile)
            self.refresh_readiness()
            if compiled["complete"]:
                log.write("[green]Profile valid: fully preconfigured image; hotspot setup wizard will be skipped.[/green]")
            else:
                log.write("[yellow]Profile valid: first-boot wizard remains enabled.[/yellow]")
                log.write("Deferred: " + ", ".join(compiled["missing"]))
            if not compiled["wifi"]["ssid"]:
                log.write("Wi-Fi blank: first boot will expose the YWD setup AP.")
        except Exception as exc:
            log.write(f"[red]Validation failed: {exc}[/red]")

    def on_input_changed(self, _event: Input.Changed) -> None:
        self.refresh_readiness()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self.do_save()
        elif event.button.id == "validate":
            self.do_validate()
        elif event.button.id == "doctor":
            self.action_run_doctor()
        elif event.button.id == "build-image":
            self.action_run_build()

    def do_task(self, argv: list[str], title: str) -> None:
        log = self.query_one("#build-log", RichLog)
        if self.task_running:
            log.write("[yellow]A builder task is already running.[/yellow]")
            return
        self.task_running = True
        log.write(f"\n[bold #45dcff]>>> {title}[/bold #45dcff]")
        log.write("$ " + " ".join(argv))

        def runner() -> None:
            try:
                p = subprocess.Popen(argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                assert p.stdout is not None
                for line in p.stdout:
                    self.call_from_thread(log.write, line.rstrip())
                rc = p.wait()
                if rc == 0:
                    self.call_from_thread(log.write, f"[green]{title} completed successfully.[/green]")
                else:
                    self.call_from_thread(log.write, f"[red]{title} failed with exit code {rc}.[/red]")
            except Exception as exc:
                self.call_from_thread(log.write, f"[red]{title} failed: {exc}[/red]")
            finally:
                self.task_running = False

        threading.Thread(target=runner, daemon=True).start()


if __name__ == "__main__":
    BuilderApp().run()
