#!/bin/sh
# Kopiert die Integration (Quelle: custom_components/haos_smart, auch für HACS)
# in den Build-Ordner der App. Vor jedem Commit ausführen, der die Integration ändert.
set -e
cd "$(dirname "$0")/.."
rm -rf haos_smart/integration
mkdir -p haos_smart/integration
cp -r custom_components/haos_smart haos_smart/integration/haos_smart
find haos_smart/integration -name __pycache__ -prune -exec rm -rf {} +
echo "Integration nach haos_smart/integration/haos_smart kopiert"
