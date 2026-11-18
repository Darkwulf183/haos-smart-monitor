# Changelog

## 0.4.0
- **Integration auf Nachfrage mitinstallieren:** Die Weboberfläche fragt beim ersten Öffnen. Bei „Ja“ kopiert die App die Integration nach `custom_components/haos_smart` und hält sie bei jedem App-Update aktuell; bei „Nein“ bleibt `/config` unberührt
- AppArmor erlaubt in der HA-Konfiguration nur den Ordner `custom_components/haos_smart`; `secrets.yaml`, `.storage` und YAML-Dateien sind gesperrt
- Die Auswahl lässt sich nur über die Weboberfläche (Ingress) ändern
- Hinweis „Home Assistant neu starten“, bis die neue Integrationsversion wirklich läuft
- Icon und Logo der Integration (ab Home Assistant 2026.3, Ordner `brand/`)
- Prüfung jedes Commits mit HACS-Validierung und hassfest

## 0.3.2
- Eigenes Icon und Logo für den App-Store (Quelle als SVG in `.github/assets`)

## 0.3.1
- Klarer Hinweis in Weboberfläche und Log, wenn die Platte wegen eingeschaltetem Schutzmodus nicht lesbar ist („Operation not permitted“)
- README und Dokumentation erklären, warum der Schutzmodus von Hand ausgeschaltet werden muss
- Erster Lauf auf echter HAOS-Hardware erfolgreich (SATA-SSD im USB-Gehäuse)

## 0.3.0 – gehärtet
- Eigenes AppArmor-Profil: nur python3 und smartctl, Platten nur lesend öffnen, keine weiteren Linux-Rechte außer `SYS_RAWIO`
- `SYS_RAWIO` ausdrücklich angefordert (für SMART über SCSI/SAT nötig; `full_access` allein gibt es nicht)
- Kein Zugriff mehr auf `/config` und kein Home-Assistant-API-Token: Die Integration wird über HACS oder von Hand installiert
- API antwortet nur noch Home Assistant Core (Gateway) und dem Supervisor (Ingress), nicht anderen Apps
- „Jetzt auslesen“ höchstens einmal pro Minute
- Option `devices` wird geprüft (nur `/dev/sdX` und `/dev/nvmeN`)
- Basisimage `alpine:3.22` per Digest gepinnt
- Integration: erkennt den Hostnamen der App selbst, Hinweis unter „Reparaturen“, wenn App- und Integrationsversion abweichen

## 0.2.0
- Weboberfläche (Übersicht + Terminal), eigene Integration statt MQTT
