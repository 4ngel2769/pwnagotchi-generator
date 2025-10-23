# Pwnagotchi Grid Test Generator

A testing framework for simulating Pwnagotchi instances that interact with the opwngrid.xyz infrastructure. This tool generates synthetic units with authentic cryptographic identities for grid testing and development purposes.

## Overview

This generator creates realistic fake Pwnagotchi units that:
- Generate valid RSA keypairs and cryptographic signatures
- Enroll with opwngrid using proper authentication
- Report simulated access point data
- Support multi-threaded AP reporting for performance
- Optionally route through Tor for anonymity

Includes a fleet management system (CLI and web interface) for controlling multiple units simultaneously.

## Key Features

**Generator**
- Authentic RSA-2048 keypair generation
- Proper PKCS1-PSS signing for enrollment
- Customizable pwned network counts
- Multi-threaded AP reporting (1-50 threads)
- Tor circuit support (one per unit)
- Persistent state management

**Fleet Manager**
- Interactive CLI for managing units
- Real-time monitoring and statistics
- Web dashboard with live updates
- Bulk operations (start/stop/reboot all)
- Tor exit node information
- **NEW:** Comprehensive edit command for all pwnie properties
- **NEW:** Tor toggle (on/off) with auto-restart
- **NEW:** Color themes (default, matrix, ocean, fire, mono)
- **NEW:** Tmux split-screen mode with live logs
- **NEW:** Batch operations on multiple units
- **NEW:** Filter and search capabilities
- **NEW:** Health checks and diagnostics
- **NEW:** Export/import fleet data
- **NEW:** Enhanced web UI with create/edit modals, status LEDs, stats graphs

## What's New in v2.0

**Color Themes** - Choose from 5 color schemes  
**Tmux Integration** - Split-screen CLI + logs  
**Enhanced Editing** - Edit all pwnie properties  
**Tor Control** - Toggle Tor on/off per pwnie  
**Advanced Stats** - Real-time graphs and metrics  
**Batch Operations** - Control multiple pwnies at once  
**Health Checks** - Fleet-wide diagnostics  
**Export/Import** - Backup and restore fleet data

See [VERSION-2.0-IMPROVEMENTS.md](readmes/VERSION-2.0-IMPROVEMENTS.md) for complete details.

## Requirements

```bash
# Core dependencies
pip3 install -r requirements.txt

# Or install manually:
pip3 install requests pycryptodome PySocks tabulate colorama

# Optional: Web UI dependencies
pip3 install flask flask-socketio python-socketio
```

## 📚 Documentation

**Quick Links:**
- [Fleet Manager Guide](readmes/FLEET-MANAGER.md) - Complete manager documentation
- [CLI Commands Reference](readmes/CLI-COMMANDS.md) - All commands with examples
- [Tmux Integration](readmes/TMUX-GUIDE.md) - Split-screen setup
- [Color Themes](readmes/COLOR-THEMES.md) - Theme customization
- [Version 2.0 Improvements](readmes/VERSION-2.0-IMPROVEMENTS.md) - What's new
- [Multi-Threading](readmes/MULTI-THREADING.md) - Performance guide
- [Installation](readmes/INSTALL.md) - Setup instructions

**Tor Support (Optional)**
```bash
# Ubuntu/Debian
sudo apt install tor

# macOS
brew install tor

# Windows
# Download from https://www.torproject.org/download/
```

## Quick Start

### Basic Generator Usage

```bash
# Generate single unit with 1M pwned networks, 20 reporting threads
python3 pwnagotchi-gen.py --count 1 --name test --pwned 1000000 --threads 20 --yes

# Generate 10 units with random stats through Tor
python3 pwnagotchi-gen.py --count 10 --tor

# Generate unit with specific pwned count
python3 pwnagotchi-gen.py --count 1 --name myunit --pwned 42
```

### Fleet Manager

```bash
# CLI interface
python3 pwnie-manager.py

# Web interface (http://localhost:5000)
python3 pwnie-manager.py --webui
```

## Command-Line Options

### Generator (`pwnagotchi-gen.py`)

```
--count N             Number of units to generate (default: 10)
--name NAME           Custom name for the unit
--pwned N             Number of pwned networks (0 to millions)
--threads N           Parallel reporting threads (1-50, default: 1)
--tor                 Route through Tor (one circuit per unit)
--interval N          Update interval in seconds (default: 60)
--api URL             Custom opwngrid API URL
--yes                 Skip confirmation prompts
```

### Fleet Manager (`pwnie-manager.py`)

```
--pwnies-dir DIR      Directory containing unit data (default: ./fake_pwnies)
--webui               Launch web interface instead of CLI
--host HOST           Web UI host (default: localhost)
--port PORT           Web UI port (default: 5000)
```

## Architecture

The system consists of three main components:

1. **Generator** (`pwnagotchi-gen.py`) - Creates and runs fake units
2. **Fleet Manager** (`pwnie-manager.py`) - Interactive CLI for management
3. **Web UI** (`pwnie_webui.py`) - Real-time web dashboard

### Data Persistence

Units save complete state to `./fake_pwnies/`:
- `{name}.json` - Unit configuration and statistics
- `{name}_private.pem` - RSA private key

State includes: enrollment token, session data, pwned count, handshakes, epochs, and reported APs.

## Multi-Threading Performance

The `--threads` flag enables parallel AP reporting for high pwned counts:

| Pwned Networks | Threads | Time        |
|----------------|---------|-------------|
| 1,000,000      | 1       | ~8 hours    |
| 1,000,000      | 20      | ~30 minutes |
| 1,000,000      | 50      | ~12 minutes |

Intelligent sampling reports 0.5-1% of total networks for counts over 100K.

## Fleet Manager Commands

Common CLI commands:
```
list              Show all units with status
boot all          Start all units
shutdown all      Stop all units
monitor           Real-time statistics view
stats             Aggregate fleet statistics
create N          Create N new units
reload            Reload units from disk
```

See `readmes/FLEET-MANAGER.md` for complete documentation.

## Documentation

- `readmes/INSTALL.md` - Detailed installation guide
- `readmes/FLEET-MANAGER.md` - Fleet manager documentation
- `readmes/MULTI-THREADING.md` - Multi-threaded reporting guide
- `readmes/CONVERSION-GUIDE.md` - Migrating from older versions
- `readmes/LINUX-QUICKSTART.md` - Linux quick reference

## Examples

### High-Volume Testing
```bash
# Create unit with 5 million pwned networks, report using 30 threads
python3 pwnagotchi-gen.py --count 1 --name mega --pwned 5000000 --threads 30 --yes --tor
```

### Anonymous Fleet
```bash
# 25 units through Tor with varying stats
python3 pwnagotchi-gen.py --count 25 --tor --pwned random
```

### Fleet Management
```bash
# Start manager, create units, monitor
python3 pwnie-manager.py
> create 10 --pwned 1000
> boot all
> monitor
```

## Technical Details

### Authentication Flow
1. Generate RSA-2048 keypair
2. Create identity: `name@fingerprint`
3. Sign identity with private key (PKCS1-PSS, SHA-256)
4. Enroll with opwngrid: POST `/api/v1/unit/enroll`
5. Receive JWT token for subsequent updates

### AP Reporting
- Initial enrollment: Report sample APs
- Ongoing: Periodically re-enroll with updated stats
- Multi-threaded: Divide APs across threads for parallel reporting

## Security Considerations

**Important Notes:**
- This tool is for testing and development only
- Tor support adds anonymity but increases startup time
- Each Tor circuit requires ~10MB RAM
- Rate limiting protection included in multi-threaded mode

## Troubleshooting

**Tor connection issues:**
```bash
# Check Tor installation
tor --version

# Stop system Tor service if conflicts occur
sudo systemctl stop tor
```

**Module not found:**
```bash
pip3 install -r requirements.txt --upgrade
```

**Port conflicts:**
Edit `TOR_SOCKS_PORT_START` in the script or stop existing Tor processes.

## License

MIT License - For testing and educational purposes only.

Based on the Pwnagotchi and pwngrid projects.
