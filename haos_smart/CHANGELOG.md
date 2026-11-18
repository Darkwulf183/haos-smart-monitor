# Changelog

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
