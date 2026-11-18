# Bewusst schlankes Alpine statt HA-Basisimage: kein s6, kein bashio nötig.
# Nur Python-Standardbibliothek + smartmontools, keine Downloads zur Laufzeit.
# Basisimage auf einen festen Stand gepinnt (alpine:3.22, Stand 18.11.2026),
# damit ein Neubau nicht unbemerkt ein anderes Image zieht.
# Aktualisieren: Digest von alpine:3.22 neu holen und hier eintragen.
FROM alpine:3.22@sha256:49340b346798875b5592e5d420241f2f9cfba5f47e62ebb1446a1b34734e898f

RUN apk add --no-cache python3 smartmontools

COPY app /app

ENV PYTHONDONTWRITEBYTECODE=1
CMD ["python3", "-u", "/app/app.py"]
