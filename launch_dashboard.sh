#!/bin/bash
# Launch Cortex Intelligence Dashboard
# Usage: ./launch_dashboard.sh

CORTEX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$CORTEX_DIR"

# Activate venv if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "🧠 Starting Cortex Intelligence Dashboard..."
echo "📊 Dashboard will open in your browser automatically"
echo ""

# Launch Streamlit
streamlit run mvp/dashboard.py \
    --server.port 8501 \
    --server.address localhost \
    --theme.base dark \
    --theme.primaryColor "#FF6B6B" \
    --theme.backgroundColor "#0E1117" \
    --theme.secondaryBackgroundColor "#262730"
