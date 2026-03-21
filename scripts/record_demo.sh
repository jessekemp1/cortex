#!/usr/bin/env bash
# Record Cortex terminal demo for README
# Usage: ./scripts/record_demo.sh
# Output: docs/assets/demo.cast (asciinema) + demo.gif (agg)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CORTEX_DIR="$(dirname "$SCRIPT_DIR")"
DEV_DIR="$(dirname "$CORTEX_DIR")"
CAST_FILE="$CORTEX_DIR/docs/assets/demo.cast"
GIF_FILE="$CORTEX_DIR/docs/assets/demo.gif"

# Create the demo script that asciinema will record
DEMO_SCRIPT=$(mktemp)
cat > "$DEMO_SCRIPT" << 'SCRIPT'
#!/usr/bin/env bash
# Cortex demo — runs from Dev root so project detection works

cd /Users/jesse/dev

type_cmd() {
    local cmd="$1"
    local delay="${2:-0.035}"
    printf "\033[1;32m❯\033[0m "
    for (( i=0; i<${#cmd}; i++ )); do
        printf "%s" "${cmd:$i:1}"
        sleep "$delay"
    done
    echo
    sleep 0.3
}

clear
sleep 0.3

# Scene 1: Morning briefing (the hook)
echo -e "\033[2m# Morning context — Cortex remembers what happened across sessions\033[0m"
sleep 1
type_cmd "cortex briefing"
python cortex/cli.py briefing 2>/dev/null | head -45
sleep 2.5

# Scene 2: Deep project intelligence
echo ""
echo -e "\033[2m# Deep analysis on any project — health score, debt, recommendations\033[0m"
sleep 1
type_cmd "cortex deep cortex"
python cortex/cli.py deep cortex 2>/dev/null
sleep 2.5

# Scene 3: Learn from this session (the loop)
echo ""
echo -e "\033[2m# Cortex learns from every session — patterns compound over time\033[0m"
sleep 1
type_cmd "cortex learn"
python cortex/cli.py learn 2>/dev/null | head -25
sleep 2.5

# Outro
echo ""
echo -e "\033[1;33m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m"
echo -e "\033[1;37m  Cortex — Persistent Intelligence for LLM Agents\033[0m"
echo -e "\033[0;37m  Every session builds on the last.  pip install cortex-intelligence\033[0m"
echo -e "\033[1;33m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m"
sleep 2
SCRIPT

chmod +x "$DEMO_SCRIPT"

echo "Recording demo to $CAST_FILE..."
asciinema rec "$CAST_FILE" \
    --command "$DEMO_SCRIPT" \
    --title "Cortex — Persistent Intelligence for LLM Agents" \
    --cols 80 \
    --rows 40 \
    --overwrite

rm -f "$DEMO_SCRIPT"

echo ""
echo "Converting to GIF..."
agg "$CAST_FILE" "$GIF_FILE" \
    --font-size 14 \
    --theme monokai \
    --speed 1.5

echo ""
echo "Done!"
echo "   Cast: $CAST_FILE"
echo "   GIF:  $GIF_FILE"
echo ""
echo "Preview: asciinema play $CAST_FILE"
