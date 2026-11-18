"""Konstanten für HAOS SMART Monitor."""
from datetime import timedelta

DOMAIN = "haos_smart"
# Muss zu "version" in manifest.json passen; die App sollte dieselbe Version haben.
INTEGRATION_VERSION = "0.4.0"

# Hostname der lokalen App im internen HA-Netz (Slug local_haos_smart)
DEFAULT_HOST = "local-haos-smart"
DEFAULT_PORT = 8099

# Die App liest die Platten selbst nur alle 30 Min. aus; die Integration holt
# öfter ab, damit ein manuelles Auslesen in der Weboberfläche bald sichtbar wird.
UPDATE_INTERVAL = timedelta(minutes=5)

REQUEST_TIMEOUT = 15
# Ein Auslesen aller Platten kann bei USB-Gehäusen etwas dauern
REFRESH_TIMEOUT = 300
