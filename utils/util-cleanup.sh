#!/bin/bash
# Utility scripts for Pwnagotchi Grid Testing

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
GRID_API="http://localhost:8666/api/v1"
OPWNGRID_API="http://opwnapi.yourdomain.tld/api/v1"
FAKE_PWNIES_DIR="./fake_pwnies"

#######################################
# Check Prerequisites
#######################################
check_prerequisites() {
    echo -e "${BLUE}=== Checking Prerequisites ===${NC}"
    
    # Check Python 3
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
        echo -e "${GREEN}✓${NC} Python 3 installed: $PYTHON_VERSION"
    else
        echo -e "${RED}✗${NC} Python 3 not found"
        exit 1
    fi
    
    # Check required Python packages
    echo -e "\n${BLUE}Checking Python packages...${NC}"
    
    for package in requests pycryptodome; do
        if python3 -c "import ${package/pycryptodome/Crypto}" 2>/dev/null; then
            echo -e "${GREEN}✓${NC} $package installed"
        else
            echo -e "${RED}✗${NC} $package not installed"
            echo "  Install with: pip3 install $package"
            exit 1
        fi
    done
    
    # Check if pwngrid is running
    echo -e "\n${BLUE}Checking pwngrid service...${NC}"
    if systemctl is-active --quiet pwngrid 2>/dev/null; then
        echo -e "${GREEN}✓${NC} pwngrid service is running"
    else
        echo -e "${YELLOW}⚠${NC} pwngrid service not detected"
        echo "  If you're using pwngrid, start it with: systemctl start pwngrid"
    fi
    
    # Test Grid API connectivity
    echo -e "\n${BLUE}Testing Grid API connectivity...${NC}"
    if curl -s -f "$GRID_API/mesh/memory" > /dev/null; then
        echo -e "${GREEN}✓${NC} Grid API is accessible"
    else
        echo -e "${RED}✗${NC} Cannot reach Grid API at $GRID_API"
        echo "  Check if pwngrid-peer is running and API URL is correct"
    fi
    
    # Test opwngrid API connectivity
    echo -e "\n${BLUE}Testing opwngrid API connectivity...${NC}"
    if curl -s -f "$OPWNGRID_API/uptime" > /dev/null; then
        echo -e "${GREEN}✓${NC} opwngrid API is accessible"
    else
        echo -e "${YELLOW}⚠${NC} Cannot reach opwngrid API at $OPWNGRID_API"
        echo "  Update OPWNGRID_API variable if needed"
    fi
    
    echo -e "\n${GREEN}Prerequisites check complete!${NC}\n"
}

#######################################
# Quick Start - Run 10 test units
#######################################
quick_start() {
    echo -e "${BLUE}=== Quick Start: 10 Test Units ===${NC}\n"
    
    # Create directory
    mkdir -p "$FAKE_PWNIES_DIR"
    
    # Run the basic test
    python3 pwny_grid_tester.py
}

#######################################
# Cleanup - Remove generated files
#######################################
cleanup() {
    echo -e "${BLUE}=== Cleanup ===${NC}\n"
    
    if [ -d "$FAKE_PWNIES_DIR" ]; then
        FILE_COUNT=$(find "$FAKE_PWNIES_DIR" -type f | wc -l)
        echo "Found $FILE_COUNT files in $FAKE_PWNIES_DIR"
        
        read -p "Delete all generated test data? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$FAKE_PWNIES_DIR"
            echo -e "${GREEN}✓${NC} Cleanup complete"
        else
            echo "Cleanup cancelled"
        fi
    else
        echo "No test data found"
    fi
}

#######################################
# Show Current Grid Status
#######################################
show_status() {
    echo -e "${BLUE}=== Current Grid Status ===${NC}\n"
    
    # Get peer count
    PEER_COUNT=$(curl -s "$GRID_API/mesh/peers" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null)
    
    if [ -n "$PEER_COUNT" ]; then
        echo -e "Active Peers: ${GREEN}$PEER_COUNT${NC}"
        
        # Show quick snapshot
        python3 grid_monitor.py --api "$GRID_API" --opwngrid "$OPWNGRID_API" snapshot
    else
        echo -e "${RED}✗${NC} Could not retrieve grid status"
    fi
}

#######################################
# Run Stress Test
#######################################
stress_test() {
    echo -e "${BLUE}=== Stress Test ===${NC}\n"
    
    read -p "How many units to spawn? (default: 50) " UNITS
    UNITS=${UNITS:-50}
    
    read -p "Spawn rate in seconds? (default: 0.1) " RATE
    RATE=${RATE:-0.1}
    
    echo -e "\nSpawning $UNITS units at ${RATE}s intervals..."
    echo -e "${YELLOW}This may take a while. Press Ctrl+C to stop.${NC}\n"
    
    python3 advanced_grid_tester.py --api "$GRID_API" --opwngrid "$OPWNGRID_API" \
        rapid-spawn --units "$UNITS" --rate "$RATE"
}

#######################################
# Monitor Mode
#######################################
monitor_mode() {
    echo -e "${BLUE}=== Monitor Mode ===${NC}\n"
    
    read -p "Update interval in seconds? (default: 30) " INTERVAL
    INTERVAL=${INTERVAL:-30}
    
    read -p "Duration in seconds? (0 = infinite) " DURATION
    DURATION=${DURATION:-0}
    
    EXPORT_FILE="grid_monitoring_$(date +%Y%m%d_%H%M%S).json"
    
    echo -e "\nStarting monitoring..."
    echo -e "Interval: ${INTERVAL}s"
    [ "$DURATION" -gt 0 ] && echo -e "Duration: ${DURATION}s" || echo -e "Duration: Infinite"
    echo -e "Export file: $EXPORT_FILE"
    echo -e "${YELLOW}Press Ctrl+C to stop${NC}\n"
    
    if [ "$DURATION" -gt 0 ]; then
        python3 grid_monitor.py --api "$GRID_API" --opwngrid "$OPWNGRID_API" \
            monitor --interval "$INTERVAL" --duration "$DURATION" --export "$EXPORT_FILE"
    else
        python3 grid_monitor.py --api "$GRID_API" --opwngrid "$OPWNGRID_API" \
            monitor --interval "$INTERVAL" --export "$EXPORT_FILE"
    fi
}

#######################################
# Interactive Menu
#######################################
show_menu() {
    clear
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║     Pwnagotchi Grid Testing - Utility Menu           ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo "1) Check Prerequisites"
    echo "2) Quick Start (10 test units)"
    echo "3) Show Grid Status"
    echo "4) Monitor Mode"
    echo "5) Run Stress Test"
    echo "6) Peer Discovery Test"
    echo "7) Intermittent Connectivity Test"
    echo "8) High Activity Test"
    echo "9) Version Diversity Test"
    echo "10) Cleanup Test Data"
    echo "0) Exit"
    echo ""
}

#######################################
# Peer Discovery Test
#######################################
peer_discovery_test() {
    echo -e "${BLUE}=== Peer Discovery Test ===${NC}\n"
    
    read -p "Number of units? (default: 10) " UNITS
    UNITS=${UNITS:-10}
    
    read -p "Duration in seconds? (default: 300) " DURATION
    DURATION=${DURATION:-300}
    
    echo -e "\nStarting peer discovery test..."
    echo -e "Units: $UNITS, Duration: ${DURATION}s"
    echo -e "${YELLOW}Press Ctrl+C to stop${NC}\n"
    
    python3 advanced_grid_tester.py --api "$GRID_API" --opwngrid "$OPWNGRID_API" \
        peer-discovery --units "$UNITS" --duration "$DURATION"
}

#######################################
# Intermittent Test
#######################################
intermittent_test() {
    echo -e "${BLUE}=== Intermittent Connectivity Test ===${NC}\n"
    
    read -p "Number of units? (default: 10) " UNITS
    UNITS=${UNITS:-10}
    
    read -p "Online duration (seconds)? (default: 120) " ON_TIME
    ON_TIME=${ON_TIME:-120}
    
    read -p "Offline duration (seconds)? (default: 60) " OFF_TIME
    OFF_TIME=${OFF_TIME:-60}
    
    read -p "Number of cycles? (default: 5) " CYCLES
    CYCLES=${CYCLES:-5}
    
    echo -e "\nStarting intermittent connectivity test..."
    echo -e "Units: $UNITS, On: ${ON_TIME}s, Off: ${OFF_TIME}s, Cycles: $CYCLES"
    echo -e "${YELLOW}Press Ctrl+C to stop${NC}\n"
    
    python3 advanced_grid_tester.py --api "$GRID_API" --opwngrid "$OPWNGRID_API" \
        intermittent --units "$UNITS" --on "$ON_TIME" --off "$OFF_TIME" --cycles "$CYCLES"
}

#######################################
# High Activity Test
#######################################
high_activity_test() {
    echo -e "${BLUE}=== High Activity Test ===${NC}\n"
    
    read -p "Duration in seconds? (default: 600) " DURATION
    DURATION=${DURATION:-600}
    
    echo -e "\nStarting high activity test..."
    echo -e "Duration: ${DURATION}s"
    echo -e "${YELLOW}This simulates a very active hunting session${NC}\n"
    
    python3 advanced_grid_tester.py --api "$GRID_API" --opwngrid "$OPWNGRID_API" \
        high-activity --duration "$DURATION"
}

#######################################
# Version Diversity Test
#######################################
version_diversity_test() {
    echo -e "${BLUE}=== Version Diversity Test ===${NC}\n"
    
    read -p "Number of units? (default: 15) " UNITS
    UNITS=${UNITS:-15}
    
    echo -e "\nStarting version diversity test..."
    echo -e "Units: $UNITS (mixed versions)"
    echo -e "${YELLOW}Press Ctrl+C to stop${NC}\n"
    
    python3 advanced_grid_tester.py --api "$GRID_API" --opwngrid "$OPWNGRID_API" \
        version-diversity --units "$UNITS"
}

#######################################
# Main Menu Loop
#######################################
main_menu() {
    while true; do
        show_menu
        read -p "Select option: " choice
        case $choice in
            1)
                check_prerequisites
                read -p "Press Enter to continue..."
                ;;
            2)
                quick_start
                read -p "Press Enter to continue..."
                ;;
            3)
                show_status
                read -p "Press Enter to continue..."
                ;;
            4)
                monitor_mode
                read -p "Press Enter to continue..."
                ;;
            5)
                stress_test
                read -p "Press Enter to continue..."
                ;;
            6)
                peer_discovery_test
                read -p "Press Enter to continue..."
                ;;
            7)
                intermittent_test
                read -p "Press Enter to continue..."
                ;;
            8)
                high_activity_test
                read -p "Press Enter to continue..."
                ;;
            9)
                version_diversity_test
                read -p "Press Enter to continue..."
                ;;
            10)
                cleanup
                read -p "Press Enter to continue..."
                ;;
            0)
                echo -e "\n${GREEN}Goodbye!${NC}\n"
                exit 0
                ;;
            *)
                echo -e "\n${RED}Invalid option${NC}\n"
                sleep 2
                ;;
        esac
    done
}

#######################################
# Command Line Interface
#######################################
if [ $# -eq 0 ]; then
    # No arguments, show interactive menu
    main_menu
else
    # Process command line arguments
    case "$1" in
        check|prerequisites)
            check_prerequisites
            ;;
        start|quick-start)
            quick_start
            ;;
        status)
            show_status
            ;;
        monitor)
            monitor_mode
            ;;
        stress)
            stress_test
            ;;
        peer-discovery)
            peer_discovery_test
            ;;
        intermittent)
            intermittent_test
            ;;
        high-activity)
            high_activity_test
            ;;
        version-diversity)
            version_diversity_test
            ;;
        cleanup|clean)
            cleanup
            ;;
        help|--help|-h)
            echo "Pwnagotchi Grid Testing Utility"
            echo ""
            echo "Usage: $0 [command]"
            echo ""
            echo "Commands:"
            echo "  check              - Check prerequisites"
            echo "  start              - Quick start with 10 units"
            echo "  status             - Show current grid status"
            echo "  monitor            - Start monitoring mode"
            echo "  stress             - Run stress test"
            echo "  peer-discovery     - Test peer discovery"
            echo "  intermittent       - Test intermittent connectivity"
            echo "  high-activity      - Test high activity unit"
            echo "  version-diversity  - Test version diversity"
            echo "  cleanup            - Clean up test data"
            echo "  help               - Show this help"
            echo ""
            echo "If no command is given, interactive menu is shown."
            ;;
        *)
            echo -e "${RED}Unknown command: $1${NC}"
            echo "Use '$0 help' for usage information"
            exit 1
            ;;
    esac
fi
