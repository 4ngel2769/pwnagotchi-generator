#!/bin/bash
#
# Real-time log monitor for Pwnagotchi Fleet
# Watches pwnie directory and displays activity
#

PWNIES_DIR="./fake_pwnies"
LOG_FILE="./fleet_activity.log"

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
RESET='\033[0m'

# Create log file if it doesn't exist
touch "$LOG_FILE"

echo -e "${CYAN}╔═══════════════════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}║     Pwnagotchi Fleet Activity Monitor                 ║${RESET}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════╝${RESET}"
echo ""

# Function to log activity
log_activity() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local message="$1"
    local color="$2"
    
    echo -e "${color}[${timestamp}]${RESET} ${message}"
    echo "[${timestamp}] ${message}" >> "$LOG_FILE"
}

# Monitor directory for changes
previous_count=0

while true; do
    if [ -d "$PWNIES_DIR" ]; then
        current_count=$(ls -1 "$PWNIES_DIR"/*.json 2>/dev/null | wc -l)
        
        if [ "$current_count" -ne "$previous_count" ]; then
            if [ "$current_count" -gt "$previous_count" ]; then
                diff=$((current_count - previous_count))
                log_activity "📦 ${diff} new pwnie(s) created (Total: ${current_count})" "$GREEN"
            else
                diff=$((previous_count - current_count))
                log_activity "🗑️  ${diff} pwnie(s) removed (Total: ${current_count})" "$RED"
            fi
            previous_count=$current_count
        fi
        
        # Show stats from random pwnie
        if [ "$current_count" -gt 0 ]; then
            random_file=$(ls "$PWNIES_DIR"/*.json 2>/dev/null | shuf -n 1)
            if [ -f "$random_file" ]; then
                pwnie_name=$(jq -r '.name // "Unknown"' "$random_file" 2>/dev/null)
                pwned=$(jq -r '.pwnd_tot // 0' "$random_file" 2>/dev/null)
                epoch=$(jq -r '.epoch // 0' "$random_file" 2>/dev/null)
                enrolled=$(jq -r '.enrolled // false' "$random_file" 2>/dev/null)
                
                timestamp=$(date '+%H:%M:%S')
                
                if [ "$enrolled" == "true" ]; then
                    status_icon="✓"
                    status_color="$GREEN"
                else
                    status_icon="✗"
                    status_color="$YELLOW"
                fi
                
                echo -e "${BLUE}[${timestamp}]${RESET} ${status_color}${status_icon}${RESET} ${CYAN}${pwnie_name}${RESET} - Pwned: ${YELLOW}${pwned}${RESET} | Epoch: ${MAGENTA}${epoch}${RESET}"
            fi
        fi
    else
        log_activity "⚠️  Pwnies directory not found" "$RED"
    fi
    
    sleep 2
done
