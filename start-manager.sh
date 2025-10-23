#!/bin/bash
# Pwnagotchi Fleet Manager - Quick Start Guide
# Bash script for Linux/macOS

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
NC='\033[0m' # No Color

echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     Pwnagotchi Fleet Manager - Quick Start                   ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check Python
echo -e "${YELLOW}[1/5] Checking Python installation...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "  ${GREEN}✓${NC} $PYTHON_VERSION"
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_VERSION=$(python --version)
    echo -e "  ${GREEN}✓${NC} $PYTHON_VERSION"
    PYTHON_CMD="python"
else
    echo -e "  ${RED}✗${NC} Python not found! Install Python 3.8+ first."
    exit 1
fi

# Check/Install dependencies
echo -e "\n${YELLOW}[2/5] Checking dependencies...${NC}"

REQUIRED_PACKAGES=("requests" "pycryptodome" "PySocks" "tabulate" "colorama")
MISSING_PACKAGES=()

for package in "${REQUIRED_PACKAGES[@]}"; do
    if $PYTHON_CMD -c "import $package" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $package"
    else
        echo -e "  ${RED}✗${NC} $package (not installed)"
        MISSING_PACKAGES+=("$package")
    fi
done

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo -e "\n  ${YELLOW}Installing missing packages...${NC}"
    
    # Try pip3 first, then pip
    if command -v pip3 &> /dev/null; then
        pip3 install "${MISSING_PACKAGES[@]}" --break-system-packages
    elif command -v pip &> /dev/null; then
        pip install "${MISSING_PACKAGES[@]}" --break-system-packages
    else
        echo -e "  ${RED}✗${NC} pip not found! Install pip first."
        exit 1
    fi
fi

# Check for existing pwnies
echo -e "\n${YELLOW}[3/5] Checking for existing pwnies...${NC}"
if [ -d "./fake_pwnies" ]; then
    PWNIE_COUNT=$(find ./fake_pwnies -name "*.json" -type f | wc -l)
    if [ "$PWNIE_COUNT" -gt 0 ]; then
        echo -e "  ${GREEN}✓${NC} Found $PWNIE_COUNT existing pwnies"
        read -p "  Create more pwnies? (y/n): " CREATE_NEW
    else
        echo -e "  ${YELLOW}ℹ${NC} No pwnies found"
        CREATE_NEW="y"
    fi
else
    echo -e "  ${YELLOW}ℹ${NC} No pwnies directory found"
    CREATE_NEW="y"
fi

# Create pwnies if needed
if [[ "$CREATE_NEW" == "y" || "$CREATE_NEW" == "Y" ]]; then
    echo -e "\n${YELLOW}[4/5] Creating pwnies...${NC}"
    
    read -p "  How many pwnies to create? (default: 10): " COUNT
    COUNT=${COUNT:-10}
    
    read -p "  Use Tor for each pwnie? (y/n, default: y): " USE_TOR
    USE_TOR=${USE_TOR:-y}
    
    read -p "  Initial pwned networks? (number or 'random', default: random): " PWNED
    PWNED=${PWNED:-random}
    
    echo -e "\n  ${CYAN}Creating $COUNT pwnies...${NC}"
    
    # Build command
    CMD="$PYTHON_CMD pwnagotchi-gen.py --count $COUNT"
    if [[ "$USE_TOR" == "y" || "$USE_TOR" == "Y" ]]; then
        CMD="$CMD --tor"
    fi
    CMD="$CMD --pwned $PWNED --yes"  # Add --yes to skip confirmation
    
    # Run for 30 seconds to let them enroll
    echo -e "  ${YELLOW}Running for 30 seconds to enroll and initialize...${NC}"
    
    # Start the process in background
    $CMD &
    PWNIE_PID=$!
    
    # Wait 30 seconds
    sleep 30
    
    # Stop the process
    kill -SIGINT $PWNIE_PID 2>/dev/null
    wait $PWNIE_PID 2>/dev/null
    
    echo -e "  ${GREEN}✓${NC} Pwnies created and saved"
else
    echo -e "\n${YELLOW}[4/5] Skipping pwnie creation${NC}"
fi

# Launch manager
echo -e "\n${YELLOW}[5/5] Launching Fleet Manager...${NC}"
echo ""

read -p "  Launch mode: [1] CLI  [2] Web UI  (default: 1): " MODE
MODE=${MODE:-1}

# Check for Web UI dependencies if needed
if [ "$MODE" == "2" ]; then
    echo -e "\n${YELLOW}Checking Web UI dependencies...${NC}"
    
    WEB_PACKAGES=("flask" "flask_socketio")
    WEB_MISSING=()
    
    for package in "${WEB_PACKAGES[@]}"; do
        if $PYTHON_CMD -c "import ${package//-/_}" 2>/dev/null; then
            echo -e "  ${GREEN}✓${NC} $package"
        else
            echo -e "  ${RED}✗${NC} $package (not installed)"
            WEB_MISSING+=("$package")
        fi
    done
    
    if [ ${#WEB_MISSING[@]} -gt 0 ]; then
        echo -e "\n  ${YELLOW}Installing Web UI dependencies...${NC}"
        
        if command -v pip3 &> /dev/null; then
            pip3 install "${WEB_MISSING[@]}" --break-system-packages
        elif command -v pip &> /dev/null; then
            pip install "${WEB_MISSING[@]}" --break-system-packages
        fi
    fi
fi

echo ""
echo -e "${CYAN}════════════════════════════════════════════════════════${NC}"

if [ "$MODE" == "2" ]; then
    echo -e "${GREEN}Starting Web UI Dashboard...${NC}"
    echo -e "${YELLOW}Open your browser to: http://localhost:5000${NC}"
    echo ""
    $PYTHON_CMD pwnie-manager.py --webui
else
    echo -e "${GREEN}Starting Interactive CLI...${NC}"
    echo ""
    echo -e "${YELLOW}Quick Commands:${NC}"
    echo -e "  ${GRAY}list        - List all pwnies${NC}"
    echo -e "  ${GRAY}boot all    - Start all pwnies${NC}"
    echo -e "  ${GRAY}monitor     - Real-time monitoring${NC}"
    echo -e "  ${GRAY}help        - Show all commands${NC}"
    echo ""
    $PYTHON_CMD pwnie-manager.py
fi

echo ""
echo -e "${CYAN}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Goodbye!${NC}"
