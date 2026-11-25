#!/usr/bin/env bash
set -euo pipefail

cd /opt/sturam_informe_diario
export PATH="/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin:$PATH"
export HOME="/home/respaldo-pi"
export USE_GEMINI_CLI=1

echo "=== [$(date '+%Y-%m-%d %H:%M:%S %Z')] Iniciando Informe Estrategico Diario STURAM ==="
/usr/bin/python3 /opt/sturam_informe_diario/main.py --send
echo "=== [$(date '+%Y-%m-%d %H:%M:%S %Z')] Finalizado con exito ==="
