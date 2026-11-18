# HAOS SMART Monitor

Überwacht per SMART **nur die Platten am Home-Assistant-Rechner** – schlank, ohne MQTT.

- **Weboberfläche** im Seitenmenü („SMART“): Übersicht pro Platte und die Rohausgabe von
  `smartctl -x` im Tab **Terminal**.
- **Sensoren in Home Assistant** über eine kleine mitgelieferte Integration: ein Gerät pro Platte,
  Sensoren im UI bearbeitbar.

## Sicherheit – bitte zuerst lesen

Die App braucht **ausgeschalteten Schutzmodus** und **vollen Hardwarezugriff**, weil der Supervisor
die Systemplatte nicht einzeln freigibt. Zusätzlich hat sie das Recht `SYS_RAWIO`, mit dem sich
ATA-Befehle – auch schreibende – direkt an Platten senden lassen. Ein eigenes AppArmor-Profil
beschränkt die App auf `python3` und `smartctl` und öffnet Platten nur lesend; Zugriff auf deine
die Home-Assistant-API hat sie nicht; auf deine Konfiguration darf sie nur im Ordner
`custom_components/haos_smart` schreiben – und auch das nur, wenn du dem Mitinstallieren zustimmst. Die ausführliche Erklärung steht in der
README des GitHub-Repositorys (Abschnitt „Sicherheit“).

## Installation

1. Repository unter **Einstellungen → Apps → App-Store → ⋮ → Repositories** hinzufügen und
   **HAOS SMART Monitor** installieren (oder lokal: Ordner `haos_smart` nach `/addons/` kopieren).
2. **Schutzmodus ausschalten** (Info-Seite der App), App (neu) starten. Das kann die App nicht selbst
   erledigen: Home Assistant lässt diese Entscheidung bewusst nur dich treffen, und nach jeder Installation
   steht der Schutzmodus auf „an“. Solange er an ist, zeigt die Weboberfläche „Operation not permitted“.
3. Weboberfläche der App öffnen und bei **„Integration mitinstallieren?“** auf **Ja** klicken. Die App kopiert
   die Integration nach `custom_components/haos_smart` und hält sie bei App-Updates aktuell (AppArmor erlaubt
   ihr nur diesen Ordner). Bei **Nein**: Integration über **HACS** oder von Hand installieren.
4. Home Assistant neu starten, dann **Einstellungen → Geräte & Dienste → Integration hinzufügen** →
   **HAOS SMART Monitor**. Host und Port werden vorgeschlagen.

## Optionen

| Option | Standard | Bedeutung |
|---|---|---|
| `scan_interval` | 30 | Alle wie viele Minuten die Platten ausgelesen werden (5–1440). |
| `devices` | leer | Leer = automatisch (`smartctl --scan-open`). Sonst Liste wie `/dev/sda` oder `/dev/sda:sat` (Gerät:Typ, für USB-Gehäuse). Nur `/dev/sdX` und `/dev/nvmeN` erlaubt. |
| `wear_warning` | 90 | Ab diesem Verschleiß (%) meldet der Zustand-Sensor ein Problem. |
| `temp_warning` | 60 | Ab dieser Temperatur (°C) meldet der Zustand-Sensor ein Problem. |
| `log_level` | info | `debug` zeigt jeden smartctl-Aufruf. |

## Entitäten pro Platte

| Entität | Hinweis |
|---|---|
| Zustand (binary_sensor, Problem) | Attribut `gruende` listet, was auffällig ist |
| Temperatur, Betriebsstunden, Verschleiß, Geschrieben, Gelesen | Hauptsensoren |
| Einschaltzyklen, Unsaubere Abschaltungen, Übertragungsfehler (CRC), Fehlerprotokoll-Einträge, Umgelagerte / Ausstehende Sektoren, Nicht korrigierbare Fehler | Diagnose |
| Letzte Abfrage | Zeitpunkt des letzten erfolgreichen Auslesens; Attribut `fehler` bei Standby o. Ä. |
| Jetzt auslesen (Button) | Lässt die App sofort alle Platten neu lesen |

Es werden nur Sensoren angelegt, die die Platte auch meldet. Neue Platten erscheinen automatisch.

### Wann meldet „Zustand“ ein Problem?

- SMART-Gesamturteil FAILED oder ein Vorausfall-Attribut unter seinem Grenzwert
- umgelagerte oder ausstehende Sektoren > 0, nicht korrigierbare Fehler > 0
- NVMe: Medienfehler > 0 oder kritische Warnung
- Verschleiß ≥ `wear_warning`, Temperatur ≥ `temp_warning`

**Kein** Problem-Kriterium sind CRC-Fehler und unsaubere Abschaltungen: Sie deuten auf Kabel,
USB-Gehäuse oder Stromversorgung hin, nicht auf einen Plattendefekt. Dafür gibt es die Sensoren –
z. B. für eine Automation „CRC-Fehler sind gestiegen“.

### Geschrieben / Gelesen

Kommen nur aus der Gerätestatistik (`Logical Sectors Written/Read` × Sektorgröße) bzw. bei NVMe
aus dem Health-Log. Attribut 241 wird bewusst nicht verwendet, weil seine Einheit vom Hersteller
abhängt. Meldet eine Platte keine Gerätestatistik, fehlen diese beiden Sensoren.

## Abfrage-Rhythmus

Die App liest die Platten alle `scan_interval` Minuten und hält das Ergebnis im Speicher. Die
Integration holt sich diese Werte alle 5 Minuten ab (ohne die Platte zu wecken). Schläft eine
Platte (Standby), wird sie nicht aufgeweckt; die letzten Werte bleiben stehen und „Letzte Abfrage“
zeigt, wie alt sie sind. Nach einem Neustart der App sind erst nach dem ersten erfolgreichen Lesen
wieder Werte da.

## API

- `GET /api/disks` – alle Platten als JSON (`?raw=1` mit Terminal-Text)
- `GET /api/disks/<id>/raw` – Textausgabe einer Platte
- `POST /api/refresh` – sofort neu auslesen; antwortet, wenn fertig (höchstens einmal pro Minute)
- `GET /api/integration` – Status der mitgelieferten Integration
- `POST /api/integration` mit `{"install": true|false}` – nur über die Weboberfläche (Ingress)

Die API antwortet nur Home Assistant Core und dem Supervisor (Ingress), nicht anderen Apps.

## Fehlersuche

- **Keine Platten gefunden / „Operation not permitted“**: Schutzmodus aus? Danach App neu starten.
  Hilft das nicht: im Host-Log (**Einstellungen → System → Protokolle → Host**) nach
  `apparmor="DENIED"` mit `haos_smart` suchen und die Zeilen als Issue melden.
- **USB-Gehäuse wird nicht erkannt**: Option `devices` auf `/dev/sda:sat` setzen.
- **NVMe-SSD**: wird bewusst nicht unterstützt (bräuchte das Recht `SYS_ADMIN`).
- **Integration lässt sich nicht hinzufügen**: Wurde Home Assistant nach dem Kopieren neu gestartet?
  Läuft die App?
- **Hinweis „unterschiedliche Versionen“ unter Reparaturen**: App und Integration auf denselben Stand
  bringen und Home Assistant neu starten.
