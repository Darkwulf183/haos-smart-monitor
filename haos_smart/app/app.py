#!/usr/bin/env python3
"""HAOS SMART Monitor – App-Kern

- liest die Platten am Home-Assistant-Rechner mit smartctl aus
- haelt die Ergebnisse im Speicher
- liefert eine Weboberflaeche (Ingress) und eine kleine JSON-API, die die
  mitgelieferte Integration abfragt

Bewusst minimal: nur Python-Standardbibliothek, kein Zugriff auf die
Home-Assistant-Konfiguration, kein Token fuer die Home-Assistant-API.
Die Integration wird separat installiert (HACS oder von Hand).
"""
import ipaddress
import json
import logging
import os
import re
import signal
import subprocess
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

VERSION = "0.3.2"
OPTIONS_FILE = os.environ.get("OPTIONS_FILE", "/data/options.json")
WEB_DIR = Path(__file__).resolve().parent / "web"
PORT = int(os.environ.get("PORT", "8099"))
# Zugriff nur fuer Home Assistant Core (kommt ueber das Gateway des internen
# Netzes) und den Supervisor (Ingress-Proxy). Andere Apps im internen Netz
# werden abgewiesen.
ALLOWED_NETS = [ipaddress.ip_network(n) for n in (
    "172.30.32.1/32", "172.30.32.2/32",            # Gateway (Core), Supervisor
    "fd0c:ac1e:2100::1/128", "fd0c:ac1e:2100::2/128",
    "127.0.0.0/8", "::1/128")]
# Erlaubte Eintraege fuer die Option "devices" (wie das Schema in config.yaml)
DEVICE_RE = re.compile(r"/dev/(sd[a-z]{1,2}|nvme[0-9]+(n[0-9]+)?)(:[a-z0-9,]+)?")
# "Jetzt auslesen" hoechstens so oft (Sekunden)
REFRESH_MIN_GAP = 60
if os.environ.get("ALLOW_ALL") == "1":  # nur fuer Tests ausserhalb von HA
    ALLOWED_NETS = [ipaddress.ip_network("0.0.0.0/0"), ipaddress.ip_network("::/0")]

log = logging.getLogger("haos_smart")


# ---------------------------------------------------------------- Optionen ---

def load_options():
    opts = {"scan_interval": 30, "devices": [], "wear_warning": 90,
            "temp_warning": 60, "log_level": "info"}
    try:
        with open(OPTIONS_FILE, encoding="utf-8") as f:
            opts.update(json.load(f))
    except FileNotFoundError:
        log.warning("Keine %s gefunden, nutze Standardwerte", OPTIONS_FILE)
    return opts


# --------------------------------------------------------------- smartctl ---

def run_smartctl(args):
    """smartctl mit JSON-Ausgabe inkl. Original-Textausgabe (Flag 'o')."""
    cmd = ["smartctl", "--json=co", *args]
    log.debug("Starte: %s", " ".join(cmd))
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except FileNotFoundError:
        log.error("smartctl nicht gefunden")
        return 255, {}
    except subprocess.TimeoutExpired:
        log.error("smartctl hat nicht geantwortet: %s", " ".join(args))
        return 255, {}
    try:
        data = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        log.error("smartctl lieferte kein JSON: %s", proc.stdout[:300])
        data = {}
    return proc.returncode, data


def discover_devices(configured):
    """Liste von (Geraet, Typ). Typ None = smartctl entscheidet."""
    if configured:
        result = []
        for entry in configured:
            entry = (entry or "").strip()
            if entry and not DEVICE_RE.fullmatch(entry):
                log.error("Ungültiger Eintrag in 'devices' ignoriert: %r", entry)
                continue
            if entry:
                name, _, dtype = entry.partition(":")
                result.append((name, dtype or None))
        return result
    _, data = run_smartctl(["--scan-open"])
    return [(d["name"], d.get("type")) for d in data.get("devices", []) if d.get("name")]


def _stats(data):
    stats = {}
    for page in (data.get("ata_device_statistics") or {}).get("pages", []):
        for entry in page.get("table", []):
            if "value" in entry and "name" in entry:
                stats[entry["name"]] = entry["value"]
    return stats


def _attrs(data):
    return {a["id"]: a for a in (data.get("ata_smart_attributes") or {}).get("table", []) if "id" in a}


def _first(*vals):
    for v in vals:
        if v is not None:
            return v
    return None


def parse(data, exit_status, opts):
    """smartctl -x JSON -> Werte, Problemgruende, Stammdaten."""
    attrs = _attrs(data)
    stats = _stats(data)

    def raw(attr_id):
        a = attrs.get(attr_id)
        return a.get("raw", {}).get("value") if a else None

    block = data.get("logical_block_size") or 512
    cap = (data.get("user_capacity") or {}).get("bytes")
    info = {
        "model": data.get("model_name") or data.get("model_family") or "Unbekannte Platte",
        "serial": data.get("serial_number"),
        "firmware": data.get("firmware_version"),
        "capacity_gb": round(cap / 1e9) if cap else None,
        "protocol": (data.get("device") or {}).get("protocol"),
        "smart_passed": (data.get("smart_status") or {}).get("passed"),
    }
    v = {
        "temperature": _first((data.get("temperature") or {}).get("current"), stats.get("Current Temperature")),
        "power_on_hours": _first((data.get("power_on_time") or {}).get("hours"), stats.get("Power-on Hours")),
        "power_cycles": _first(data.get("power_cycle_count"), stats.get("Lifetime Power-On Resets")),
    }

    nvme = data.get("nvme_smart_health_information_log")
    critical_warning = 0
    if nvme:
        # NVMe: eine "data unit" sind 1000 x 512 Byte
        v["wear_used"] = nvme.get("percentage_used")
        if nvme.get("data_units_written") is not None:
            v["data_written_tb"] = round(nvme["data_units_written"] * 512000 / 1e12, 3)
        if nvme.get("data_units_read") is not None:
            v["data_read_tb"] = round(nvme["data_units_read"] * 512000 / 1e12, 3)
        v["unsafe_shutdowns"] = nvme.get("unsafe_shutdowns")
        v["media_errors"] = nvme.get("media_errors")
        v["available_spare"] = nvme.get("available_spare")
        v["error_log_entries"] = nvme.get("num_err_log_entries")
        critical_warning = nvme.get("critical_warning") or 0
    else:
        v["wear_used"] = stats.get("Percentage Used Endurance Indicator")
        # Nur die Geraetestatistik hat eine verlaessliche Einheit. Attribut 241
        # ist herstellerabhaengig und wird bewusst NICHT genutzt.
        if stats.get("Logical Sectors Written") is not None:
            v["data_written_tb"] = round(stats["Logical Sectors Written"] * block / 1e12, 3)
        if stats.get("Logical Sectors Read") is not None:
            v["data_read_tb"] = round(stats["Logical Sectors Read"] * block / 1e12, 3)
        v["reallocated_sectors"] = raw(5)
        v["pending_sectors"] = raw(197)
        v["uncorrectable"] = _first(stats.get("Number of Reported Uncorrectable Errors"), raw(187))
        v["crc_errors"] = _first(stats.get("Number of Interface CRC Errors"), raw(199))
        v["unsafe_shutdowns"] = _first(raw(174), raw(192))
        err_log = data.get("ata_smart_error_log") or {}
        v["error_log_entries"] = (err_log.get("extended") or err_log.get("summary") or {}).get("count")

    reasons = []
    if info["smart_passed"] is False or exit_status & 0b1000:
        reasons.append("SMART-Gesamturteil: FAILED")
    if exit_status & 0b10000:
        reasons.append("Vorausfall-Attribut unter Grenzwert")
    for key, text in (("reallocated_sectors", "umgelagerte Sektoren"),
                      ("pending_sectors", "ausstehende Sektoren"),
                      ("uncorrectable", "nicht korrigierbare Fehler"),
                      ("media_errors", "Medienfehler")):
        if (v.get(key) or 0) > 0:
            reasons.append(f"{v[key]} {text}")
    if critical_warning:
        reasons.append(f"NVMe-Warnung (Code {critical_warning})")
    if v.get("wear_used") is not None and v["wear_used"] >= opts["wear_warning"]:
        reasons.append(f"Verschleiß {v['wear_used']} %")
    if v.get("temperature") is not None and v["temperature"] >= opts["temp_warning"]:
        reasons.append(f"Temperatur {v['temperature']} °C")

    return info, {k: val for k, val in v.items() if val is not None}, reasons


def disk_id(serial, device):
    return re.sub(r"[^a-z0-9_]", "_", (serial or device).lower()).strip("_")


# ------------------------------------------------------------- Ausleser ---

class Monitor:
    def __init__(self, opts):
        self.opts = opts
        self.lock = threading.Lock()
        self.disks = {}          # id -> Ergebnis
        self.last_scan = None
        self.last_scan_mono = None
        self.scanning = False
        self.wake = threading.Event()
        self.scan_done = threading.Condition()
        self.generation = 0

    def read_disk(self, device, dtype):
        args = ["-x", "-n", "standby"]
        if dtype:
            args += ["-d", dtype]
        args.append(device)
        status, data = run_smartctl(args)
        output = "\n".join(line.rstrip("\n") for line in (data.get("smartctl") or {}).get("output", []))
        messages = [m.get("string", "") for m in (data.get("smartctl") or {}).get("messages", [])]
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")

        if status & 0b10 and not data.get("smart_status"):
            err = "; ".join(messages) or f"smartctl-Status {status}"
            if "Operation not permitted" in err:
                # Typisch bei eingeschaltetem Schutzmodus: dann gibt der Supervisor
                # den vollen Hardwarezugriff nicht frei.
                err += (" – Der Schutzmodus der App ist vermutlich noch eingeschaltet. "
                        "Auf der Info-Seite der App ausschalten und die App neu starten.")
            log.warning("%s nicht lesbar oder im Standby: %s", device, err)
            return {"id": disk_id(None, device), "device": device, "type": dtype,
                    "error": err, "raw": output, "checked": now}

        info, values, reasons = parse(data, status, self.opts)
        return {
            "id": disk_id(info["serial"], device),
            "device": device,
            "type": dtype or (data.get("device") or {}).get("type"),
            **info,
            "values": values,
            "problem": bool(reasons),
            "reasons": reasons,
            "exit_status": status,
            "raw": output,
            "last_update": now,
            "checked": now,
            "error": None,
        }

    def scan(self):
        with self.lock:
            self.scanning = True
        try:
            devices = discover_devices(self.opts.get("devices") or [])
            if not devices:
                log.warning("Keine Platten gefunden. Hat die App vollen Hardwarezugriff?")
            results = {}
            for device, dtype in devices:
                try:
                    r = self.read_disk(device, dtype)
                except Exception:
                    log.exception("Fehler beim Auslesen von %s", device)
                    continue
                if r.get("error"):
                    # alte Werte behalten (z. B. Platte im Standby), Fehler vermerken
                    with self.lock:
                        old = next((d for d in self.disks.values()
                                    if d["device"] == device and d.get("values")), None)
                    if old:
                        r = {**old, "error": r["error"], "checked": r["checked"]}
                else:
                    log.info("%s (%s): %s, %s h, %s °C, Verschleiß %s %%",
                             device, r["model"],
                             "PROBLEM: " + ", ".join(r["reasons"]) if r["reasons"] else "OK",
                             r["values"].get("power_on_hours"), r["values"].get("temperature"),
                             r["values"].get("wear_used"))
                results[r["id"]] = r
            with self.lock:
                self.disks = results
                self.last_scan = datetime.now(timezone.utc).isoformat(timespec="seconds")
                self.last_scan_mono = time.monotonic()
        finally:
            with self.lock:
                self.scanning = False
            with self.scan_done:
                self.generation += 1
                self.scan_done.notify_all()

    def run(self, stop):
        while not stop.is_set():
            self.scan()
            self.wake.wait(self.opts["scan_interval"] * 60)
            self.wake.clear()

    def refresh_now(self, timeout=240):
        """Sofort auslesen; hoechstens alle REFRESH_MIN_GAP Sekunden."""
        with self.lock:
            last = self.last_scan_mono
        if last is not None and time.monotonic() - last < REFRESH_MIN_GAP and not self.scanning:
            log.debug("Auslesen angefordert, letzte Abfrage ist juenger als %s s", REFRESH_MIN_GAP)
            return
        with self.scan_done:
            target = self.generation + 1 + (1 if self.scanning else 0)
            self.wake.set()
            self.scan_done.wait_for(lambda: self.generation >= target, timeout=timeout)

    def snapshot(self, with_raw=False):
        with self.lock:
            disks = []
            for d in self.disks.values():
                d = dict(d)
                if not with_raw:
                    d.pop("raw", None)
                disks.append(d)
            return {"version": VERSION, "last_scan": self.last_scan,
                    "scanning": self.scanning, "interval_min": self.opts["scan_interval"],
                    "disks": sorted(disks, key=lambda x: x["device"])}


# ------------------------------------------------------------- Webserver ---

def make_handler(monitor):
    index_html = (WEB_DIR / "index.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        server_version = f"haos_smart/{VERSION}"

        def log_message(self, fmt, *args):
            log.debug("HTTP %s - %s", self.client_address[0], fmt % args)

        def _allowed(self):
            try:
                ip = ipaddress.ip_address(self.client_address[0])
            except ValueError:
                return False
            if any(ip in net for net in ALLOWED_NETS):
                return True
            self.send_error(403, "Nur aus Home Assistant erreichbar")
            return False

        def _send(self, code, body, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code=200):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def do_GET(self):
            if not self._allowed():
                return
            path = self.path.split("?", 1)[0].rstrip("/") or "/"
            if path in ("/", "/index.html"):
                self._send(200, index_html, "text/html; charset=utf-8")
            elif path == "/favicon.ico":
                self._send(204, b"", "image/x-icon")
            elif path == "/api/disks":
                self._json(monitor.snapshot(with_raw="raw=1" in self.path))
            elif path.startswith("/api/disks/") and path.endswith("/raw"):
                did = path.split("/")[3]
                with monitor.lock:
                    disk = monitor.disks.get(did)
                if not disk:
                    self._json({"error": "unbekannte Platte"}, 404)
                else:
                    self._send(200, (disk.get("raw") or "").encode(), "text/plain; charset=utf-8")
            else:
                self._json({"error": "nicht gefunden"}, 404)

        def do_POST(self):
            if not self._allowed():
                return
            path = self.path.split("?", 1)[0].rstrip("/")
            if path == "/api/refresh":
                monitor.refresh_now()
                self._json(monitor.snapshot())
            else:
                self._json({"error": "nicht gefunden"}, 404)

    return Handler


# ------------------------------------------------------------------ Start ---

def main():
    opts = load_options()
    logging.basicConfig(
        level=getattr(logging, str(opts["log_level"]).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    log.info("HAOS SMART Monitor %s startet (Intervall %s min)", VERSION, opts["scan_interval"])

    stop = threading.Event()
    monitor = Monitor(opts)
    threading.Thread(target=monitor.run, args=(stop,), daemon=True).start()

    server = ThreadingHTTPServer(("0.0.0.0", PORT), make_handler(monitor))
    server.daemon_threads = True

    def shutdown(*_):
        log.info("Beende ...")
        stop.set()
        monitor.wake.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    log.info("Weboberfläche bereit auf Port %s", PORT)
    server.serve_forever()


if __name__ == "__main__":
    main()
