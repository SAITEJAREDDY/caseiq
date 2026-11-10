#!/usr/bin/env bash
# Start CaseIQ: check both Neo4j databases first, then launch the Streamlit app.
#   ./start.sh                 main app on http://localhost:8501 (includes the Diagnostic Agent page)
#   ./start.sh --dashboard     also start the measurement dashboard on http://localhost:8502
# Both databases are hosted (Neo4j Aura), so nothing is started locally: the check tells you what is wrong if one is paused or gone.
cd "$(dirname "$0")" || exit 1
PY="./.venv/bin/python3"; [ -x "$PY" ] || PY="python3"
echo "Checking Neo4j databases..."
"$PY" -m agent.neo4j_health || echo "⚠  Continuing anyway: a page that needs an unreachable database will say so."
if [ "${1:-}" = "--dashboard" ]; then
  "$PY" -m streamlit run measurement_dashboard.py --server.port 8502 --server.headless true &
fi
exec "$PY" -m streamlit run app.py
