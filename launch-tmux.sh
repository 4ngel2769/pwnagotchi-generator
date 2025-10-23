#!/bin/bash
#
# Tmux launcher for Pwnagotchi Fleet Manager
# Splits terminal into left (CLI) and right (logs) panes
#

SESSION_NAME="pwnie-fleet"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    echo "Error: tmux is not installed. Install it with:"
    echo "  Ubuntu/Debian: sudo apt-get install tmux"
    echo "  macOS: brew install tmux"
    echo "  Windows: Use WSL or install via scoop/chocolatey"
    exit 1
fi

# Kill existing session if it exists
tmux kill-session -t "$SESSION_NAME" 2>/dev/null

# Create new session with split panes
tmux new-session -d -s "$SESSION_NAME" -x 200 -y 50

# Split window vertically (left/right)
tmux split-window -h -t "$SESSION_NAME"

# Set pane sizes (60% left, 40% right)
tmux select-layout -t "$SESSION_NAME" main-vertical

# Left pane: Fleet Manager CLI
tmux send-keys -t "$SESSION_NAME:0.0" "cd '$SCRIPT_DIR'" C-m
tmux send-keys -t "$SESSION_NAME:0.0" "python3 pwnie-manager.py" C-m

# Right pane: Log viewer
tmux send-keys -t "$SESSION_NAME:0.1" "cd '$SCRIPT_DIR'" C-m
tmux send-keys -t "$SESSION_NAME:0.1" "# Pwnie Fleet Logs" C-m
tmux send-keys -t "$SESSION_NAME:0.1" "# Logs will appear here when implemented" C-m
tmux send-keys -t "$SESSION_NAME:0.1" "echo ''" C-m
tmux send-keys -t "$SESSION_NAME:0.1" "echo 'Monitoring pwnie activity...'" C-m
tmux send-keys -t "$SESSION_NAME:0.1" "echo 'Press Ctrl+C to stop monitoring'" C-m
tmux send-keys -t "$SESSION_NAME:0.1" "echo ''" C-m

# Optional: Start a log monitoring script if it exists
if [ -f "$SCRIPT_DIR/monitor-logs.sh" ]; then
    tmux send-keys -t "$SESSION_NAME:0.1" "./monitor-logs.sh" C-m
else
    # Fallback: tail the pwnies directory for changes
    tmux send-keys -t "$SESSION_NAME:0.1" "watch -n 1 'ls -lh fake_pwnies/*.json 2>/dev/null | tail -20'" C-m
fi

# Set pane titles
tmux select-pane -t "$SESSION_NAME:0.0" -T "Fleet Manager"
tmux select-pane -t "$SESSION_NAME:0.1" -T "Activity Logs"

# Focus on left pane (CLI)
tmux select-pane -t "$SESSION_NAME:0.0"

# Attach to session
echo "Launching Pwnie Fleet Manager in tmux..."
echo "Use Ctrl+B then arrow keys to switch panes"
echo "Use Ctrl+B then 'd' to detach from session"
echo "Use 'tmux attach -t $SESSION_NAME' to reattach"
echo ""

tmux attach-session -t "$SESSION_NAME"
