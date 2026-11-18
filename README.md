<p align="center"><img src="haos_smart/logo.png" alt="HAOS SMART Monitor" width="250"></p>

# HAOS SMART Monitor

Schlanke Home-Assistant-App, die per SMART **nur die Platten am Home-Assistant-Rechner** überwacht –
mit eigener Weboberfläche und Sensoren in Home Assistant, **ohne MQTT**.

> **⚠️ Bitte vor der Installation den Abschnitt [Sicherheit](#sicherheit) lesen.**
> Die App braucht **ausgeschalteten Schutzmodus** und **vollen Hardwarezugriff**. Unten steht genau,
> was das bedeutet, warum es nicht anders geht und was die App dagegen tut.

*English summary: Minimal app + integration that reads SMART data of the disks in your Home Assistant OS
machine. It requires protection mode to be disabled and full hardware access – please read the
security section before installing.*

---

## Was sie kann

- **Weboberfläche** im Seitenmenü („SMART“): Übersicht pro Platte und die Rohausgabe von `smartctl -x`
  im Tab **Terminal**, hell/dunkel.
- **Sensoren in Home Assistant** über die mitgelieferte Integration: ein Gerät pro Platte mit
  Zustand (Problem-Sensor mit Begründung), Temperatur, Betriebsstunden, Verschleiß,
  Geschrieben/Gelesen und Diagnose-Zählern. Neue Platten erscheinen automatisch.
- Weckt keine schlafenden Platten auf (`-n standby`).
- Nur Python-Standardbibliothek und smartmontools, keine weiteren Pakete, keine Verbindungen ins Internet.

**Unterstützt:** SATA-Platten und SSDs, auch im USB-Gehäuse (SAT).
**Nicht unterstützt:** NVMe – das bräuchte ein weiteres, sehr weitreichendes Linux-Recht (siehe unten).

---

## Sicherheit

### Kurzfassung

SMART-Werte lassen sich nur mit **direktem Zugriff auf die Platte** lesen. Unter Home Assistant OS
geht das für die Systemplatte nur mit **vollem Hardwarezugriff**, und der funktioniert nur bei
**ausgeschaltetem Schutzmodus**. Home Assistant zeigt deshalb für diese App die
**niedrigste Sicherheitsbewertung (1)** an. Das gilt genauso für andere SMART-Apps wie Scrutiny.

Wer der App diese Rechte gibt, vertraut ihrem Code. Ist der Code (oder das Basisimage) manipuliert,
könnte er im schlimmsten Fall **Daten auf jeder Platte im Rechner verändern oder zerstören**.
Die App ist deshalb so gebaut, dass möglichst wenig Code mit möglichst wenigen Rechten läuft – und
dass du alles selbst nachlesen kannst.

**Installiere die App nicht, wenn** du dem Code in diesem Repository nicht vertraust oder ihn nicht
prüfen lassen willst, oder wenn dir eine SMART-Warnung den Kompromiss nicht wert ist.

### Warum der Schutzmodus aus sein muss

- Home Assistant kann einer App einzelne Geräte freigeben (`devices`). Der Supervisor **verweigert das
  aber für die Systemplatte** – also genau die Platte, um die es hier geht.
- Bleibt nur `full_access`. Das wirkt laut Supervisor ausschließlich bei ausgeschaltetem Schutzmodus.
- Zusätzlich braucht `smartctl` das Linux-Recht `SYS_RAWIO`, um ATA-Befehle an die Platte zu schicken
  (bei SSDs im USB-Gehäuse über SCSI/SAT).

### Was „voller Hardwarezugriff“ hier konkret bedeutet

Im aktuellen Supervisor ist `full_access` **kein** privilegierter Docker-Container. Es bewirkt:

| | |
|---|---|
| **Gerätezugriff** | Die App darf alle Gerätedateien unter `/dev` öffnen (statt nur einzelner). |
| **Linux-Rechte** | Keine zusätzlichen – außer dem ausdrücklich angeforderten `SYS_RAWIO`. |
| **AppArmor** | Bleibt aktiv; die App bringt ein eigenes, strenges Profil mit. |

`SYS_RAWIO` erlaubt, beliebige ATA/SCSI-Befehle an eine Platte zu senden – **auch schreibende**.
Das lässt sich nicht weiter einschränken, weil SMART genau über diesen Weg gelesen wird.

### Was die App bewusst **nicht** hat

| Recht | Status |
|---|---|
| Lesen/Schreiben deiner HA-Konfiguration (`secrets.yaml`, `.storage`, YAML-Dateien) | ❌ per AppArmor gesperrt – erlaubt ist nur der eigene Ordner `custom_components/haos_smart`, und auch der erst nach deiner Zustimmung (siehe unten) |
| Token für die Home-Assistant- oder Supervisor-API | ❌ nicht angefordert |
| Docker-API, Host-Netzwerk, Host-Prozesse | ❌ |
| `SYS_ADMIN` (u. a. Dateisysteme einhängen) | ❌ – deshalb auch kein NVMe |
| Offener Port nach außen | ❌ nur über Ingress (mit HA-Anmeldung) und das interne Netz |
| Python-Pakete von Dritten, Downloads zur Laufzeit | ❌ |

### Was die App dagegen tut

- **AppArmor-Profil** ([`haos_smart/apparmor.txt`](haos_smart/apparmor.txt)): Es dürfen nur `python3`
  und `smartctl` laufen. Platten werden nur **lesend** geöffnet, Schreiben auf `/dev/sd*` und
  `/dev/nvme*` ist verboten, ebenso `/dev/mem`, Raw-Sockets und alle Linux-Rechte außer `SYS_RAWIO`.
  Hinweis: Befehle, die über `SYS_RAWIO` direkt an die Platte gehen, kann AppArmor nicht filtern.
- **API nur für Home Assistant**: Die Schnittstelle antwortet nur Anfragen über das Gateway des
  internen Netzes (dort kommen Home Assistant Core und Apps mit Host-Netzwerk an) und vom Supervisor
  (Ingress). Andere Apps im internen Netz werden abgewiesen. Sie liefert nur Daten und
  kann nichts verändern; „Jetzt auslesen“ ist auf einmal pro Minute begrenzt.
- **Eingaben geprüft**: Die Option `devices` akzeptiert nur `/dev/sdX` bzw. `/dev/nvmeN`
  (optional mit `:typ`). `smartctl` wird ohne Shell aufgerufen.
- **Wenig Code**: rund 400 Zeilen Python ([`haos_smart/app/app.py`](haos_smart/app/app.py)) plus eine
  HTML-Datei. Keine Abhängigkeiten außer Python und smartmontools aus Alpine Linux.
- **Integration nur auf Nachfrage**: `/config` ist eingebunden, damit die App ihre Integration mitinstallieren
  kann. Sie tut das aber erst, wenn du in der Weboberfläche **„Ja, mitinstallieren“** wählst. Diese Auswahl lässt
  sich nur über die Weboberfläche (also angemeldet in Home Assistant) ändern, nicht über die API von anderen
  Apps. AppArmor beschränkt das Schreiben auf `custom_components/haos_smart`; ehrlich gesagt ist diese Sperre
  genau so gut wie AppArmor selbst. Wer das nicht möchte, wählt „Nein“ und installiert die Integration über HACS.
- **Kein fertiges Image**: Home Assistant baut das Image bei der Installation auf deinem Rechner aus
  genau den Dateien in diesem Repository. Das Basisimage (`alpine:3.22`) ist auf einen festen Stand
  (Digest) gepinnt.

### Selbst prüfen

1. `haos_smart/config.yaml` ansehen: welche Rechte angefordert werden.
2. `haos_smart/apparmor.txt` ansehen: was die App darf.
3. `haos_smart/app/app.py` lesen: was sie tut.
4. Nach der Installation unter **Einstellungen → Apps → HAOS SMART Monitor → Info** steht, welche
   Rechte die App tatsächlich hat.

### Sicherheitsproblem gefunden?

Bitte **nicht** als öffentliches Issue melden, sondern über
**Security → Report a vulnerability** in diesem Repository.

---

## Installation

### 1. App

1. **Einstellungen → Apps → App-Store** → ⋮ (oben rechts) → **Repositories** →
   `https://github.com/Darkwulf183/haos-smart-monitor` hinzufügen.
2. **HAOS SMART Monitor** installieren.
3. Auf der Info-Seite der App den **Schutzmodus ausschalten** (siehe unten und [Sicherheit](#sicherheit)).
4. App (neu) starten und im Log prüfen, dass die Platte gefunden wurde.

#### Warum muss ich den Schutzmodus selbst ausschalten?

Eine App **kann** den Schutzmodus nicht selbst abschalten – auch nicht als Voreinstellung. In Home Assistant
ist er eine Einstellung, die nur du triffst, und sie steht nach jeder Installation auf „an“. Das ist Absicht:
Ob eine App Zugriff auf die Hardware bekommt, soll immer bewusst der Mensch entscheiden, nicht der Entwickler
der App.

Solange der Schutzmodus an ist, startet die App zwar, bekommt aber keinen Zugriff auf die Platte. In der
Weboberfläche steht dann **„Nicht lesbar … Operation not permitted“** mit dem Hinweis, den Schutzmodus
auszuschalten. Nach dem Ausschalten die App **neu starten** – der Zugriff gilt erst ab dem nächsten Start.

### 2. Integration (für Sensoren in Home Assistant)

**Am einfachsten:** Weboberfläche der App öffnen (Seitenmenü „SMART“ oder „Web-UI öffnen“). Beim ersten Mal
fragt sie **„Integration mitinstallieren?“** → **Ja**. Die App kopiert die Integration und hält sie bei jedem
App-Update aktuell. Danach Home Assistant neu starten – die Weboberfläche erinnert dich daran, bis der Neustart
erfolgt ist. Die Auswahl lässt sich unten in der Weboberfläche über „ändern“ jederzeit anpassen.

Alternativ, wenn du „Nein“ wählst:

- **HACS:** HACS → ⋮ → **Benutzerdefinierte Repositories** → dieses Repository als
  **Integration** hinzufügen → **HAOS SMART Monitor** herunterladen.
- **Von Hand:** Den Ordner `custom_components/haos_smart` nach `/config/custom_components/haos_smart`
  kopieren (z. B. mit Studio Code Server oder Samba).

Danach Home Assistant **neu starten** und unter **Einstellungen → Geräte & Dienste → Integration
hinzufügen** → **HAOS SMART Monitor** wählen. Host und Port werden automatisch vorgeschlagen.

App und Integration sollten dieselbe Version haben. Weichen sie ab, erscheint ein Hinweis unter
**Einstellungen → Reparaturen** (bei der Variante „mitinstallieren“ passiert das nicht).

Ab Home Assistant 2026.3 zeigt die Integration ihr eigenes Icon an.

---

## Entitäten pro Platte

| Entität | Hinweis |
|---|---|
| **Zustand** (binary_sensor, Problem) | Attribut `gruende` listet, was auffällig ist |
| Temperatur, Betriebsstunden, Verschleiß, Geschrieben, Gelesen | Hauptsensoren |
| Einschaltzyklen, Unsaubere Abschaltungen, Übertragungsfehler (CRC), Fehlerprotokoll-Einträge, Umgelagerte / Ausstehende Sektoren, Nicht korrigierbare Fehler | Diagnose |
| Letzte Abfrage | Zeitpunkt des letzten erfolgreichen Auslesens |
| Jetzt auslesen (Button) | Lässt die App sofort neu lesen |

**Zustand meldet ein Problem bei:** SMART-Gesamturteil FAILED, Vorausfall-Attribut unter Grenzwert,
umgelagerten oder ausstehenden Sektoren, nicht korrigierbaren Fehlern, Verschleiß ≥ 90 % oder
Temperatur ≥ 60 °C (beides einstellbar).
CRC-Fehler und unsaubere Abschaltungen sind **kein** Problem-Kriterium – sie deuten auf Kabel,
USB-Gehäuse oder Stromversorgung hin. Dafür gibt es die Diagnose-Sensoren.

Mehr Details (Optionen, Fehlersuche, API): [haos_smart/DOCS.md](haos_smart/DOCS.md).

---

## Aufbau des Repositorys

```
repository.yaml                  App-Repository für Home Assistant
haos_smart/                      die App (config.yaml, Dockerfile, apparmor.txt, app/)
haos_smart/integration/          Kopie der Integration für das App-Image (scripts/sync_integration.sh)
custom_components/haos_smart/    die Integration (Quelle, auch für HACS), mit brand/-Icons
hacs.json
.github/workflows/               Release automatisch je Version, Prüfung mit HACS + hassfest
```

---

## Lizenz

GPL-3.0 – siehe [LICENSE](LICENSE). Copyright © 2026 Ralf N.
