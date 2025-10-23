#!/usr/bin/env python3
"""
Pwnagotchi Fleet Manager - Interactive Terminal Application
Manage, monitor, and control fake Pwnagotchi instances

Features:
- List all pwnies with detailed status
- Boot up/shut down individual or all pwnies
- Add pwned networks to existing pwnies
- View Tor status, exit nodes, and IPs
- Monitor real-time stats
- Configure individual pwnies
- Web UI dashboard (optional)
"""

import os
import sys
import json
import time
import threading
import argparse
import requests
import subprocess
import shutil
import logging
import importlib.util
from datetime import datetime
from pathlib import Path
from cmd import Cmd
from tabulate import tabulate
from collections import defaultdict

# Configure logging to suppress console output
logging.basicConfig(level=logging.WARNING)
logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('socketio').setLevel(logging.ERROR)
logging.getLogger('engineio').setLevel(logging.ERROR)

# Try to import colorama for Windows color support
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    COLORS_ENABLED = True
except ImportError:
    COLORS_ENABLED = False
    # Fallback color class
    class Fore:
        RED = GREEN = YELLOW = BLUE = CYAN = MAGENTA = WHITE = RESET = ''
    class Style:
        BRIGHT = DIM = RESET_ALL = ''

# Import from main script
try:
    import pwnagotchi_gen as pwn_gen
    FakePwnagotchi = pwn_gen.FakePwnagotchi
    OPWNGRID_API_URL = pwn_gen.OPWNGRID_API_URL
    TOR_SOCKS_PORT_START = pwn_gen.TOR_SOCKS_PORT_START
except ImportError:
    # If running standalone, we'll need to handle this differently
    import importlib.util
    spec = importlib.util.spec_from_file_location("pwnagotchi_gen", "./pwnagotchi-gen.py")
    if spec and spec.loader:
        pwn_gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pwn_gen)
        FakePwnagotchi = pwn_gen.FakePwnagotchi
        OPWNGRID_API_URL = pwn_gen.OPWNGRID_API_URL
        TOR_SOCKS_PORT_START = pwn_gen.TOR_SOCKS_PORT_START
    else:
        OPWNGRID_API_URL = "https://your.opwngrid-api-url.com/api/v1"
        TOR_SOCKS_PORT_START = 9050
        FakePwnagotchi = None

# Configuration
PWNIES_DIR = "./fake_pwnies"
STATE_FILE = "./pwnies_state.json"
CONFIG_FILE = "./fleet_config.json"

# Color themes
COLOR_THEMES = {
    'default': {
        'primary': Fore.CYAN,
        'success': Fore.GREEN,
        'warning': Fore.YELLOW,
        'error': Fore.RED,
        'info': Fore.BLUE,
        'highlight': Fore.MAGENTA,
    },
    'matrix': {
        'primary': Fore.GREEN,
        'success': Fore.GREEN + Style.BRIGHT,
        'warning': Fore.GREEN,
        'error': Fore.RED,
        'info': Fore.GREEN,
        'highlight': Fore.WHITE + Style.BRIGHT,
    },
    'ocean': {
        'primary': Fore.CYAN,
        'success': Fore.BLUE + Style.BRIGHT,
        'warning': Fore.YELLOW,
        'error': Fore.RED,
        'info': Fore.CYAN + Style.BRIGHT,
        'highlight': Fore.MAGENTA,
    },
    'fire': {
        'primary': Fore.RED,
        'success': Fore.YELLOW + Style.BRIGHT,
        'warning': Fore.YELLOW,
        'error': Fore.RED + Style.BRIGHT,
        'info': Fore.MAGENTA,
        'highlight': Fore.WHITE + Style.BRIGHT,
    },
    'mono': {
        'primary': Fore.WHITE,
        'success': Fore.WHITE + Style.BRIGHT,
        'warning': Fore.WHITE,
        'error': Fore.WHITE + Style.BRIGHT,
        'info': Fore.WHITE,
        'highlight': Fore.WHITE + Style.BRIGHT,
    },
}

# Active theme (can be changed via config)
ACTIVE_THEME = 'default'


def get_color(color_type):
    """Get color for current theme"""
    return COLOR_THEMES.get(ACTIVE_THEME, COLOR_THEMES['default']).get(color_type, Fore.WHITE)


class FleetConfig:
    """Manager configuration"""
    
    def __init__(self, config_file=CONFIG_FILE):
        self.config_file = Path(config_file)
        self.config = self.load()
    
    def load(self):
        """Load configuration from file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        
        # Default configuration
        return {
            'theme': 'default',
            'log_level': 'WARNING',
            'update_interval': 2,
            'enable_sounds': False,
        }
    
    def save(self):
        """Save configuration to file"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def set(self, key, value):
        """Set configuration value"""
        self.config[key] = value
        self.save()
    
    def get(self, key, default=None):
        """Get configuration value"""
        return self.config.get(key, default)


class PwnieManager:
    """Manages the lifecycle and state of fake pwnagotchis"""
    
    def __init__(self, pwnies_dir=PWNIES_DIR):
        self.pwnies_dir = Path(pwnies_dir)
        self.pwnies = {}  # pwnie_id -> FakePwnagotchi instance
        self.threads = {}  # pwnie_id -> thread
        self.state_file = Path(STATE_FILE)
        self.load_pwnies()
    
    def load_pwnies(self):
        """Load all pwnies from disk"""
        if not self.pwnies_dir.exists():
            print(f"{Fore.YELLOW}No pwnies directory found. Create some pwnies first!{Style.RESET_ALL}")
            return
        
        # Load each pwnie from JSON files
        for pwnie_file in self.pwnies_dir.glob("*.json"):
            try:
                with open(pwnie_file, 'r') as f:
                    data = json.load(f)
                
                # Skip files missing critical fields (old generator format)
                if 'public_key' not in data:
                    print(f"{Fore.YELLOW}Skipping {pwnie_file.name}: old format, missing public_key{Style.RESET_ALL}")
                    continue
                
                pwnie_id = data.get('id', 0)
                
                # Recreate FakePwnagotchi instance from saved data
                pwnie = FakePwnagotchi(
                    pwny_id=pwnie_id,
                    opwngrid_url=OPWNGRID_API_URL,
                    use_tor=data.get('use_tor', False),
                    tor_port=data.get('tor_port'),
                    custom_pwned=data.get('pwnd_tot', 0)
                )
                
                # Restore saved state
                pwnie.name = data['name']
                pwnie.fingerprint = data['fingerprint']
                pwnie.identity = data.get('identity', f"{data['name']}@{data['fingerprint']}")
                pwnie.public_key = data['public_key']
                pwnie.enrolled = data.get('enrolled', False)
                pwnie.token = data.get('token', '')
                pwnie.pwnd_tot = data.get('pwnd_tot', 0)
                pwnie.pwnd_run = data.get('pwnd_run', 0)
                pwnie.epoch = data.get('epoch', 0)
                pwnie.uptime = data.get('uptime', 0)
                pwnie.version = data.get('version', '1.5.5')
                pwnie.personality = data.get('personality', 'balanced')
                pwnie.session_data = data.get('session_data', {
                    'deauthed': 0,
                    'associated': 0,
                    'handshakes': 0,
                    'peers': 0,
                })
                pwnie.access_points = data.get('access_points', [])
                
                # Load private key
                key_file = self.pwnies_dir / f"{pwnie.name}_private.pem"
                if key_file.exists():
                    with open(key_file, 'rb') as f:
                        from Crypto.PublicKey import RSA
                        pwnie.private_key = RSA.import_key(f.read())
                
                # Generate unique ID from name to avoid collisions
                import hashlib
                unique_id = int(hashlib.md5(pwnie.name.encode()).hexdigest()[:8], 16) % 100000
                self.pwnies[unique_id] = pwnie
                pwnie.pwny_id = unique_id  # Update the ID
                
            except Exception as e:
                print(f"{Fore.RED}Error loading {pwnie_file.name}: {e}{Style.RESET_ALL}")
        
        print(f"{Fore.GREEN}Loaded {len(self.pwnies)} pwnies from disk{Style.RESET_ALL}")
    
    def save_pwnie(self, pwnie_id):
        """Save a single pwnie's state to disk"""
        if pwnie_id not in self.pwnies:
            return False
        
        pwnie = self.pwnies[pwnie_id]
        
        try:
            # Save JSON data
            data = {
                'id': pwnie_id,
                'name': pwnie.name,
                'fingerprint': pwnie.fingerprint,
                'public_key': pwnie.public_key,
                'enrolled': pwnie.enrolled,
                'token': pwnie.token,
                'pwnd_tot': pwnie.pwnd_tot,
                'pwnd_run': pwnie.pwnd_run,
                'epoch': pwnie.epoch,
                'uptime': pwnie.uptime,
                'version': pwnie.version,
                'personality': pwnie.personality,
                'use_tor': pwnie.use_tor,
                'tor_port': pwnie.tor_port,
                'session_data': pwnie.session_data,
                'access_points': pwnie.access_points,
                'last_saved': datetime.now().isoformat(),
            }
            
            json_file = self.pwnies_dir / f"{pwnie.name}.json"
            with open(json_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True
        except Exception as e:
            print(f"{Fore.RED}Error saving pwnie {pwnie.name}: {e}{Style.RESET_ALL}")
            return False
    
    def save_all(self):
        """Save all pwnies to disk"""
        for pwnie_id in self.pwnies:
            self.save_pwnie(pwnie_id)
    
    def boot_pwnie(self, pwnie_id):
        """Start a pwnie's update thread"""
        if pwnie_id not in self.pwnies:
            return False, "Pwnie not found"
        
        if pwnie_id in self.threads and self.threads[pwnie_id].is_alive():
            return False, "Pwnie already running"
        
        pwnie = self.pwnies[pwnie_id]
        
        # Start the run thread
        thread = threading.Thread(target=pwnie.run, daemon=True)
        thread.start()
        self.threads[pwnie_id] = thread
        
        return True, f"Pwnie {pwnie.name} started"
    
    def shutdown_pwnie(self, pwnie_id):
        """Stop a pwnie's update thread"""
        if pwnie_id not in self.pwnies:
            return False, "Pwnie not found"
        
        pwnie = self.pwnies[pwnie_id]
        pwnie.stop()
        
        # Wait for thread to finish
        if pwnie_id in self.threads:
            self.threads[pwnie_id].join(timeout=5)
        
        # Save state before shutdown
        self.save_pwnie(pwnie_id)
        
        return True, f"Pwnie {pwnie.name} stopped"
    
    def boot_all(self):
        """Start all pwnies"""
        count = 0
        for pwnie_id in self.pwnies:
            success, _ = self.boot_pwnie(pwnie_id)
            if success:
                count += 1
        return count
    
    def shutdown_all(self):
        """Stop all pwnies"""
        count = 0
        for pwnie_id in self.pwnies:
            success, _ = self.shutdown_pwnie(pwnie_id)
            if success:
                count += 1
        return count
    
    def add_pwned_networks(self, pwnie_id, count):
        """Add additional pwned networks to a pwnie"""
        if pwnie_id not in self.pwnies:
            return False, "Pwnie not found"
        
        pwnie = self.pwnies[pwnie_id]
        
        # Generate and report new APs
        for i in range(count):
            essid, bssid = pwnie._generate_fake_ap()
            pwnie.access_points.append({'essid': essid, 'bssid': bssid})
            
            # If enrolled, report the AP
            if pwnie.enrolled:
                pwnie.report_ap(essid, bssid)
            
            time.sleep(0.5)  # Small delay between reports
        
        pwnie.pwnd_tot += count
        self.save_pwnie(pwnie_id)
        
        return True, f"Added {count} networks to {pwnie.name}"
    
    def get_tor_info(self, pwnie_id):
        """Get Tor status and exit node info for a pwnie"""
        if pwnie_id not in self.pwnies:
            return None
        
        pwnie = self.pwnies[pwnie_id]
        
        if not pwnie.use_tor or not pwnie.tor_process:
            return {
                'enabled': False,
                'status': 'disabled',
            }
        
        # Check if Tor process is running
        running = pwnie.tor_process.poll() is None
        
        info = {
            'enabled': True,
            'status': 'running' if running else 'stopped',
            'port': pwnie.tor_port,
            'exit_ip': None,
            'exit_country': None,
        }
        
        if running:
            try:
                # Get exit IP through Tor
                proxies = {
                    'http': f'socks5h://127.0.0.1:{pwnie.tor_port}',
                    'https': f'socks5h://127.0.0.1:{pwnie.tor_port}',
                }
                
                # Get IP
                response = requests.get('https://api.ipify.org?format=json', 
                                       proxies=proxies, timeout=10)
                info['exit_ip'] = response.json().get('ip')
                
                # Get country
                response = requests.get(f'https://ipapi.co/{info["exit_ip"]}/json/', 
                                       timeout=10)
                data = response.json()
                info['exit_country'] = data.get('country_name', 'Unknown')
                info['exit_city'] = data.get('city', 'Unknown')
                
            except Exception as e:
                info['error'] = str(e)
        
        return info
    
    def get_pwnie_status(self, pwnie_id):
        """Get comprehensive status of a pwnie"""
        if pwnie_id not in self.pwnies:
            return None
        
        pwnie = self.pwnies[pwnie_id]
        is_running = pwnie_id in self.threads and self.threads[pwnie_id].is_alive()
        
        return {
            'id': pwnie_id,
            'name': pwnie.name,
            'fingerprint': pwnie.fingerprint[:16] + '...',
            'running': is_running,
            'enrolled': pwnie.enrolled,
            'version': pwnie.version,
            'personality': pwnie.personality,
            'pwned': pwnie.pwnd_tot,
            'epoch': pwnie.epoch,
            'uptime': pwnie.uptime,
            'deauths': pwnie.session_data.get('deauthed', 0),
            'associations': pwnie.session_data.get('associated', 0),
            'handshakes': pwnie.session_data.get('handshakes', 0),
            'aps_count': len(pwnie.access_points),
            'use_tor': pwnie.use_tor,
        }
    
    def list_all(self):
        """Get status of all pwnies"""
        return [self.get_pwnie_status(pid) for pid in sorted(self.pwnies.keys())]
    
    def reboot_pwnie(self, pwnie_id):
        """Reboot a pwnie (stop and start)"""
        success, msg = self.shutdown_pwnie(pwnie_id)
        if not success:
            return False, msg
        
        time.sleep(2)
        
        return self.boot_pwnie(pwnie_id)
    
    def create_pwnie(self, name='', pwned=0, use_tor=False, threads=1):
        """Create a new pwnie"""
        import subprocess
        import sys
        
        try:
            # Build command
            cmd = [sys.executable, 'pwnagotchi-gen.py', '--count', '1']
            
            if name:
                cmd.extend(['--name', name])
            
            if pwned > 0:
                cmd.extend(['--pwned', str(pwned)])
            
            if threads > 1:
                cmd.extend(['--threads', str(threads)])
            
            if use_tor:
                cmd.append('--tor')
            
            cmd.append('--yes')
            
            # Run generator
            print(f"Creating pwnie... (this may take a moment)")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                # Reload pwnies from disk
                self.load_pwnies()
                return True, f"Pwnie created successfully! Total pwnies: {len(self.pwnies)}"
            else:
                return False, f"Failed to create pwnie: {result.stderr}"
        
        except Exception as e:
            return False, f"Error creating pwnie: {str(e)}"
    
    def edit_pwnie(self, pwnie_id, settings):
        """Edit pwnie settings - supports all editable fields"""
        if pwnie_id not in self.pwnies:
            return False, "Pwnie not found"
        
        pwnie = self.pwnies[pwnie_id]
        was_running = pwnie_id in self.threads and self.threads[pwnie_id].is_alive()
        
        # Stop if running
        if was_running:
            self.shutdown_pwnie(pwnie_id)
            time.sleep(1)
        
        changes = []
        
        # Update name (requires file rename)
        if 'name' in settings and settings['name'] != pwnie.name:
            old_name = pwnie.name
            old_file = self.pwnies_dir / f"{old_name}.json"
            pwnie.name = settings['name']
            new_file = self.pwnies_dir / f"{pwnie.name}.json"
            if old_file.exists():
                old_file.rename(new_file)
            changes.append(f"name: {old_name} → {pwnie.name}")
        
        # Update personality
        if 'personality' in settings and settings['personality'] in ['aggressive', 'passive', 'balanced']:
            old_pers = pwnie.personality
            pwnie.personality = settings['personality']
            changes.append(f"personality: {old_pers} → {pwnie.personality}")
        
        # Update version
        if 'version' in settings:
            old_ver = pwnie.version
            pwnie.version = settings['version']
            changes.append(f"version: {old_ver} → {pwnie.version}")
        
        # Update Tor
        if 'use_tor' in settings:
            old_tor = pwnie.use_tor
            pwnie.use_tor = settings['use_tor']
            # Allocate Tor port if enabling
            if pwnie.use_tor and not pwnie.tor_port:
                pwnie.tor_port = TOR_SOCKS_PORT_START + pwnie_id
            changes.append(f"tor: {old_tor} → {pwnie.use_tor}")
        
        # Update threads
        if 'threads' in settings:
            old_threads = getattr(pwnie, 'report_threads', 1)
            pwnie.report_threads = settings.get('threads', 1)
            changes.append(f"threads: {old_threads} → {pwnie.report_threads}")
        
        # Update pwned count
        if 'pwned' in settings:
            old_pwned = pwnie.pwnd_tot
            pwnie.pwnd_tot = settings['pwned']
            pwnie.session_data['handshakes'] = pwnie.pwnd_tot
            changes.append(f"pwned: {old_pwned} → {pwnie.pwnd_tot}")
        
        # Update epoch
        if 'epoch' in settings:
            old_epoch = pwnie.epoch
            pwnie.epoch = settings['epoch']
            pwnie.session_data['epochs'] = pwnie.epoch
            changes.append(f"epoch: {old_epoch} → {pwnie.epoch}")
        
        # Add networks if requested
        if settings.get('add_networks', 0) > 0:
            count = settings['add_networks']
            pwnie.pwnd_tot += count
            pwnie.session_data['handshakes'] = pwnie.pwnd_tot
            changes.append(f"added {count} networks")
        
        # Save changes
        self.save_pwnie(pwnie_id)
        
        # Restart if it was running
        if was_running:
            time.sleep(1)
            self.boot_pwnie(pwnie_id)
            msg = f"Pwnie updated and restarted: {', '.join(changes)}"
        else:
            msg = f"Pwnie updated: {', '.join(changes)}"
        
        return True, msg if changes else "No changes made"
    
    def enable_tor_failsafe(self):
        """Enable Tor for all non-Tor pwnies and restart them"""
        affected = []
        
        for pwnie_id, pwnie in self.pwnies.items():
            if not pwnie.use_tor:
                was_running = pwnie_id in self.threads and self.threads[pwnie_id].is_alive()
                
                # Stop if running
                if was_running:
                    self.shutdown_pwnie(pwnie_id)
                    time.sleep(0.5)
                
                # Enable Tor
                pwnie.use_tor = True
                if not pwnie.tor_port:
                    pwnie.tor_port = TOR_SOCKS_PORT_START + pwnie_id
                
                self.save_pwnie(pwnie_id)
                
                # Restart
                if was_running:
                    time.sleep(0.5)
                    self.boot_pwnie(pwnie_id)
                
                affected.append(pwnie.name)
        
        if affected:
            return True, f"Tor failsafe enabled for: {', '.join(affected)}", len(affected)
        else:
            return True, "All pwnies already using Tor", 0
    
    def get_stats_history(self):
        """Get historical stats for graphing (stub for now)"""
        # This would track stats over time in a real implementation
        # For now, return current stats
        pwnies = self.list_all()
        return {
            'current': {
                'total_pwned': sum(p['pwned'] for p in pwnies),
                'total_handshakes': sum(p['handshakes'] for p in pwnies),
                'total_deauths': sum(p['deauths'] for p in pwnies),
                'running': sum(1 for p in pwnies if p['running']),
                'stopped': sum(1 for p in pwnies if not p['running']),
            }
        }
    
    def toggle_tor(self, pwnie_id, enable):
        """Toggle Tor for a specific pwnie"""
        if pwnie_id not in self.pwnies:
            return False, "Pwnie not found"
        
        pwnie = self.pwnies[pwnie_id]
        was_running = pwnie_id in self.threads and self.threads[pwnie_id].is_alive()
        
        # Check if already in desired state
        if enable and pwnie.use_tor:
            return True, "Tor already enabled", was_running
        if not enable and not pwnie.use_tor:
            return True, "Tor already disabled", was_running
        
        # Update Tor setting
        pwnie.use_tor = enable
        
        if enable:
            # Allocate Tor port if enabling
            if not pwnie.tor_port:
                pwnie.tor_port = TOR_SOCKS_PORT_START + pwnie_id
        
        # Save changes
        self.save_pwnie(pwnie_id)
        
        action = "enabled" if enable else "disabled"
        return True, f"Tor {action} for {pwnie.name}", was_running


class PwnieManagerCLI(Cmd):
    """Interactive command-line interface for pwnie management"""
    
    # Note: intro and prompt are set in __init__ after theme is loaded
    intro = ""
    prompt = ""
    
    def __init__(self, manager, config=None):
        super().__init__()
        self.manager = manager
        self.config = config or FleetConfig()
        
        # Apply theme from config
        global ACTIVE_THEME
        ACTIVE_THEME = self.config.get('theme', 'default')
        
        # Set intro and prompt with theme colors
        self.intro = f"""
{get_color('primary')}╔═══════════════════════════════════════════════════════════════╗
║          Pwnagotchi Fleet Manager v2.0.0                      ║
║          Interactive Management Console                        ║
╚═══════════════════════════════════════════════════════════════╝{Style.RESET_ALL}

Type 'help' or '?' to list commands.
Type 'exit' or 'quit' to exit.
"""
        
        # Update prompt with theme
        self.prompt = f'{get_color("success")}pwnie-fleet> {Style.RESET_ALL}'
    
    def do_list(self, arg):
        """List all pwnies with their status
        Usage: list [--detailed]
        """
        detailed = '--detailed' in arg
        
        pwnies = self.manager.list_all()
        
        if not pwnies:
            print(f"{Fore.YELLOW}No pwnies found. Create some first!{Style.RESET_ALL}")
            return
        
        if detailed:
            # Detailed view
            for pwnie in pwnies:
                self._print_pwnie_detailed(pwnie)
        else:
            # Table view
            headers = ['ID', 'Name', 'Status', 'Enrolled', 'Pwned', 'Epoch', 'Tor', 'Version']
            rows = []
            
            for p in pwnies:
                status = f"{Fore.GREEN}●{Fore.RESET} Running" if p['running'] else f"{Fore.RED}●{Fore.RESET} Stopped"
                enrolled = f"{Fore.GREEN}✓{Fore.RESET}" if p['enrolled'] else f"{Fore.RED}✗{Fore.RESET}"
                tor = f"{Fore.GREEN}✓{Fore.RESET}" if p['use_tor'] else f"{Fore.RED}✗{Fore.RESET}"
                
                rows.append([
                    p['id'],
                    p['name'],
                    status,
                    enrolled,
                    p['pwned'],
                    p['epoch'],
                    tor,
                    p['version'],
                ])
            
            print(tabulate(rows, headers=headers, tablefmt='simple'))
    
    def _print_pwnie_detailed(self, pwnie):
        """Print detailed info for a single pwnie"""
        print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Pwnie ID: {pwnie['id']} - {pwnie['name']}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        
        status_color = Fore.GREEN if pwnie['running'] else Fore.RED
        print(f"Status:        {status_color}{'RUNNING' if pwnie['running'] else 'STOPPED'}{Style.RESET_ALL}")
        print(f"Enrolled:      {Fore.GREEN if pwnie['enrolled'] else Fore.RED}{'Yes' if pwnie['enrolled'] else 'No'}{Style.RESET_ALL}")
        print(f"Fingerprint:   {pwnie['fingerprint']}")
        print(f"Version:       {pwnie['version']}")
        print(f"Personality:   {pwnie['personality']}")
        print(f"\n{Fore.YELLOW}Statistics:{Style.RESET_ALL}")
        print(f"  Pwned Networks:  {pwnie['pwned']}")
        print(f"  Epoch:           {pwnie['epoch']}")
        print(f"  Uptime:          {pwnie['uptime']}s")
        print(f"  Deauths:         {pwnie['deauths']}")
        print(f"  Associations:    {pwnie['associations']}")
        print(f"  Handshakes:      {pwnie['handshakes']}")
        print(f"  APs Tracked:     {pwnie['aps_count']}")
        
        if pwnie['use_tor']:
            print(f"\n{Fore.MAGENTA}Tor Status:{Style.RESET_ALL}")
            tor_info = self.manager.get_tor_info(pwnie['id'])
            if tor_info:
                print(f"  Status:    {tor_info['status']}")
                if tor_info.get('exit_ip'):
                    print(f"  Exit IP:   {tor_info['exit_ip']}")
                    print(f"  Country:   {tor_info.get('exit_country', 'Unknown')}")
                    print(f"  City:      {tor_info.get('exit_city', 'Unknown')}")
    
    def do_info(self, arg):
        """Show detailed information for a specific pwnie
        Usage: info <pwnie_id>
        """
        if not arg:
            print(f"{Fore.RED}Error: Provide a pwnie ID{Style.RESET_ALL}")
            return
        
        try:
            pwnie_id = int(arg)
            pwnie = self.manager.get_pwnie_status(pwnie_id)
            
            if not pwnie:
                print(f"{Fore.RED}Error: Pwnie {pwnie_id} not found{Style.RESET_ALL}")
                return
            
            self._print_pwnie_detailed(pwnie)
            
        except ValueError:
            print(f"{Fore.RED}Error: Invalid pwnie ID{Style.RESET_ALL}")
    
    def do_boot(self, arg):
        """Boot up one or all pwnies
        Usage: boot <pwnie_id|all>
        """
        if not arg:
            print(f"{Fore.RED}Error: Specify pwnie ID or 'all'{Style.RESET_ALL}")
            return
        
        if arg.lower() == 'all':
            count = self.manager.boot_all()
            print(f"{Fore.GREEN}Started {count} pwnies{Style.RESET_ALL}")
        else:
            try:
                pwnie_id = int(arg)
                success, msg = self.manager.boot_pwnie(pwnie_id)
                
                if success:
                    print(f"{Fore.GREEN}{msg}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}{msg}{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Error: Invalid pwnie ID{Style.RESET_ALL}")
    
    def do_shutdown(self, arg):
        """Shutdown one or all pwnies
        Usage: shutdown <pwnie_id|all>
        """
        if not arg:
            print(f"{Fore.RED}Error: Specify pwnie ID or 'all'{Style.RESET_ALL}")
            return
        
        if arg.lower() == 'all':
            count = self.manager.shutdown_all()
            print(f"{Fore.GREEN}Stopped {count} pwnies{Style.RESET_ALL}")
        else:
            try:
                pwnie_id = int(arg)
                success, msg = self.manager.shutdown_pwnie(pwnie_id)
                
                if success:
                    print(f"{Fore.GREEN}{msg}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}{msg}{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Error: Invalid pwnie ID{Style.RESET_ALL}")
    
    def do_reboot(self, arg):
        """Reboot a pwnie
        Usage: reboot <pwnie_id>
        """
        if not arg:
            print(f"{Fore.RED}Error: Specify pwnie ID{Style.RESET_ALL}")
            return
        
        try:
            pwnie_id = int(arg)
            success, msg = self.manager.reboot_pwnie(pwnie_id)
            
            if success:
                print(f"{Fore.GREEN}{msg}{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}{msg}{Style.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Error: Invalid pwnie ID{Style.RESET_ALL}")
    
    def do_addnets(self, arg):
        """Add pwned networks to a pwnie
        Usage: addnets <pwnie_id> <count>
        """
        parts = arg.split()
        
        if len(parts) != 2:
            print(f"{Fore.RED}Error: Usage: addnets <pwnie_id> <count>{Style.RESET_ALL}")
            return
        
        try:
            pwnie_id = int(parts[0])
            count = int(parts[1])
            
            if count < 1 or count > 100:
                print(f"{Fore.RED}Error: Count must be between 1 and 100{Style.RESET_ALL}")
                return
            
            print(f"{Fore.YELLOW}Adding {count} networks to pwnie {pwnie_id}...{Style.RESET_ALL}")
            success, msg = self.manager.add_pwned_networks(pwnie_id, count)
            
            if success:
                print(f"{Fore.GREEN}{msg}{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}{msg}{Style.RESET_ALL}")
                
        except ValueError:
            print(f"{Fore.RED}Error: Invalid pwnie ID or count{Style.RESET_ALL}")
    
    def do_tor(self, arg):
        """Show or toggle Tor status for a pwnie
        Usage: tor <pwnie_id> [on|off]
        
        Examples:
          tor 1         - Show Tor status for pwnie 1
          tor 1 on      - Enable Tor for pwnie 1
          tor 1 off     - Disable Tor for pwnie 1
        """
        if not arg:
            print(f"{Fore.RED}Error: Specify pwnie ID{Style.RESET_ALL}")
            return
        
        parts = arg.split()
        
        try:
            pwnie_id = int(parts[0])
            
            # Check if pwnie exists
            pwnie = self.manager.get_pwnie_status(pwnie_id)
            if not pwnie:
                print(f"{Fore.RED}Error: Pwnie {pwnie_id} not found{Style.RESET_ALL}")
                return
            
            # Toggle mode
            if len(parts) == 2 and parts[1].lower() in ['on', 'off']:
                enable = parts[1].lower() == 'on'
                
                success, msg, was_running = self.manager.toggle_tor(pwnie_id, enable)
                
                if not success:
                    print(f"{Fore.RED}Error: {msg}{Style.RESET_ALL}")
                    return
                
                print(f"{Fore.GREEN}{msg}{Style.RESET_ALL}")
                
                # Prompt for restart if pwnie is running
                if was_running:
                    action = "enable" if enable else "disable"
                    confirm = input(f"\n{Fore.YELLOW}Pwnie is currently running. Restart now to {action} Tor? (yes/no): {Style.RESET_ALL}")
                    
                    if confirm.lower() == 'yes':
                        print(f"{Fore.YELLOW}Restarting pwnie...{Style.RESET_ALL}")
                        success, restart_msg = self.manager.reboot_pwnie(pwnie_id)
                        if success:
                            print(f"{Fore.GREEN}{restart_msg}{Style.RESET_ALL}")
                        else:
                            print(f"{Fore.RED}Restart failed: {restart_msg}{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.YELLOW}Restart skipped. Changes will take effect on next boot.{Style.RESET_ALL}")
                
                return
            
            # Show status mode
            tor_info = self.manager.get_tor_info(pwnie_id)
            
            if not tor_info:
                print(f"{Fore.RED}Error: Could not retrieve Tor info{Style.RESET_ALL}")
                return
            
            if not tor_info['enabled']:
                print(f"{Fore.YELLOW}Tor is disabled for this pwnie{Style.RESET_ALL}")
                print(f"\n{get_color('info')}💡 To enable Tor: {Style.BRIGHT}tor {pwnie_id} on{Style.RESET_ALL}")
                return
            
            print(f"\n{Fore.MAGENTA}Tor Status for Pwnie {pwnie_id}:{Style.RESET_ALL}")
            print(f"  Status:      {Fore.GREEN if tor_info['status'] == 'running' else Fore.RED}{tor_info['status']}{Style.RESET_ALL}")
            print(f"  SOCKS Port:  {tor_info['port']}")
            
            if tor_info.get('exit_ip'):
                print(f"  Exit IP:     {tor_info['exit_ip']}")
                print(f"  Country:     {tor_info.get('exit_country', 'Unknown')}")
                print(f"  City:        {tor_info.get('exit_city', 'Unknown')}")
            
            if 'error' in tor_info:
                print(f"  {Fore.RED}Error: {tor_info['error']}{Style.RESET_ALL}")
            
            print(f"\n{get_color('info')}💡 To disable Tor: {Style.BRIGHT}tor {pwnie_id} off{Style.RESET_ALL}")
                
        except ValueError:
            print(f"{Fore.RED}Error: Invalid pwnie ID{Style.RESET_ALL}")
    
    def do_edit(self, arg):
        """Edit pwnie properties interactively
        Usage: edit <pwnie_id>
        
        Allows editing of: name, personality, version, threads, pwned count
        """
        if not arg:
            print(f"{Fore.RED}Error: Specify pwnie ID{Style.RESET_ALL}")
            return
        
        try:
            pwnie_id = int(arg)
            
            if pwnie_id not in self.manager.pwnies:
                print(f"{Fore.RED}Error: Pwnie {pwnie_id} not found{Style.RESET_ALL}")
                return
            
            pwnie = self.manager.pwnies[pwnie_id]
            was_running = pwnie_id in self.manager.threads and self.manager.threads[pwnie_id].is_alive()
            
            print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Editing Pwnie {pwnie_id}: {pwnie.name}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Leave blank to keep current value. Type 'cancel' to abort.{Style.RESET_ALL}\n")
            
            # Show current values and prompt for new ones
            # Name
            new_name = input(f"Name [{Fore.CYAN}{pwnie.name}{Style.RESET_ALL}]: ").strip()
            if new_name.lower() == 'cancel':
                print(f"{Fore.YELLOW}Edit cancelled{Style.RESET_ALL}")
                return
            
            # Personality
            current_pers = pwnie.personality
            personalities = ['aggressive', 'passive', 'balanced']
            print(f"\nPersonality options: {', '.join(personalities)}")
            new_personality = input(f"Personality [{Fore.CYAN}{current_pers}{Style.RESET_ALL}]: ").strip().lower()
            if new_personality == 'cancel':
                print(f"{Fore.YELLOW}Edit cancelled{Style.RESET_ALL}")
                return
            
            # Version
            new_version = input(f"Version [{Fore.CYAN}{pwnie.version}{Style.RESET_ALL}]: ").strip()
            if new_version.lower() == 'cancel':
                print(f"{Fore.YELLOW}Edit cancelled{Style.RESET_ALL}")
                return
            
            # Report threads
            threads = getattr(pwnie, 'report_threads', 1)
            new_threads = input(f"Report Threads [{Fore.CYAN}{threads}{Style.RESET_ALL}]: ").strip()
            if new_threads.lower() == 'cancel':
                print(f"{Fore.YELLOW}Edit cancelled{Style.RESET_ALL}")
                return
            
            # Pwned count
            new_pwned = input(f"Pwned Networks [{Fore.CYAN}{pwnie.pwnd_tot}{Style.RESET_ALL}]: ").strip()
            if new_pwned.lower() == 'cancel':
                print(f"{Fore.YELLOW}Edit cancelled{Style.RESET_ALL}")
                return
            
            # Epoch
            new_epoch = input(f"Epoch [{Fore.CYAN}{pwnie.epoch}{Style.RESET_ALL}]: ").strip()
            if new_epoch.lower() == 'cancel':
                print(f"{Fore.YELLOW}Edit cancelled{Style.RESET_ALL}")
                return
            
            # Apply changes
            changes_made = False
            
            if was_running:
                print(f"\n{Fore.YELLOW}Stopping pwnie to apply changes...{Style.RESET_ALL}")
                self.manager.shutdown_pwnie(pwnie_id)
                time.sleep(1)
            
            if new_name and new_name != pwnie.name:
                # Rename JSON file
                old_file = self.manager.pwnies_dir / f"{pwnie.name}.json"
                pwnie.name = new_name
                new_file = self.manager.pwnies_dir / f"{pwnie.name}.json"
                if old_file.exists():
                    old_file.rename(new_file)
                changes_made = True
                print(f"{Fore.GREEN}✓ Name updated to: {new_name}{Style.RESET_ALL}")
            
            if new_personality and new_personality in personalities and new_personality != current_pers:
                pwnie.personality = new_personality
                changes_made = True
                print(f"{Fore.GREEN}✓ Personality updated to: {new_personality}{Style.RESET_ALL}")
            
            if new_version and new_version != pwnie.version:
                pwnie.version = new_version
                changes_made = True
                print(f"{Fore.GREEN}✓ Version updated to: {new_version}{Style.RESET_ALL}")
            
            if new_threads and new_threads.isdigit():
                new_threads_val = int(new_threads)
                if 1 <= new_threads_val <= 10:
                    pwnie.report_threads = new_threads_val
                    changes_made = True
                    print(f"{Fore.GREEN}✓ Threads updated to: {new_threads_val}{Style.RESET_ALL}")
            
            if new_pwned and new_pwned.isdigit():
                new_pwned_val = int(new_pwned)
                pwnie.pwnd_tot = new_pwned_val
                pwnie.session_data['handshakes'] = new_pwned_val
                changes_made = True
                print(f"{Fore.GREEN}✓ Pwned count updated to: {new_pwned_val}{Style.RESET_ALL}")
            
            if new_epoch and new_epoch.isdigit():
                pwnie.epoch = int(new_epoch)
                pwnie.session_data['epochs'] = pwnie.epoch
                changes_made = True
                print(f"{Fore.GREEN}✓ Epoch updated to: {new_epoch}{Style.RESET_ALL}")
            
            if changes_made:
                self.manager.save_pwnie(pwnie_id)
                print(f"\n{Fore.GREEN}✓ Changes saved{Style.RESET_ALL}")
                
                if was_running:
                    confirm = input(f"\n{Fore.YELLOW}Restart pwnie now? (yes/no): {Style.RESET_ALL}")
                    if confirm.lower() == 'yes':
                        self.manager.boot_pwnie(pwnie_id)
                        print(f"{Fore.GREEN}✓ Pwnie restarted{Style.RESET_ALL}")
            else:
                print(f"\n{Fore.YELLOW}No changes made{Style.RESET_ALL}")
                if was_running:
                    self.manager.boot_pwnie(pwnie_id)
                    print(f"{Fore.GREEN}✓ Pwnie restarted{Style.RESET_ALL}")
                
        except ValueError:
            print(f"{Fore.RED}Error: Invalid pwnie ID{Style.RESET_ALL}")
    
    def do_logs(self, arg):
        """View logs for a specific pwnie or all pwnies
        Usage: logs [pwnie_id] [--lines N] [--follow]
        
        Examples:
          logs             - Show last 50 lines from all pwnies
          logs 1           - Show last 50 lines from pwnie 1
          logs 1 --lines 100  - Show last 100 lines
          logs --follow    - Follow all logs in real-time (Ctrl+C to stop)
        """
        # This would require implementing a logging system for pwnies
        print(f"{get_color('warning')}Logging system not yet implemented{Style.RESET_ALL}")
        print(f"{get_color('info')}💡 Use tmux mode for live log viewing: {Style.BRIGHT}python pwnie-manager.py --tmux{Style.RESET_ALL}")
    
    def do_export(self, arg):
        """Export pwnie data to JSON
        Usage: export [pwnie_id|all] [filename]
        
        Examples:
          export all                  - Export all to pwnies_export.json
          export 1                    - Export pwnie 1 to pwnie_1.json
          export all my_backup.json   - Export all to custom file
        """
        parts = arg.split()
        
        if not parts:
            print(f"{Fore.RED}Error: Specify 'all' or pwnie ID{Style.RESET_ALL}")
            return
        
        target = parts[0]
        filename = parts[1] if len(parts) > 1 else None
        
        try:
            if target.lower() == 'all':
                pwnies = self.manager.list_all()
                filename = filename or 'pwnies_export.json'
                
                with open(filename, 'w') as f:
                    json.dump(pwnies, f, indent=2)
                
                print(f"{Fore.GREEN}✓ Exported {len(pwnies)} pwnies to {filename}{Style.RESET_ALL}")
            
            else:
                pwnie_id = int(target)
                pwnie = self.manager.get_pwnie_status(pwnie_id)
                
                if not pwnie:
                    print(f"{Fore.RED}Error: Pwnie {pwnie_id} not found{Style.RESET_ALL}")
                    return
                
                filename = filename or f'pwnie_{pwnie_id}.json'
                
                with open(filename, 'w') as f:
                    json.dump(pwnie, f, indent=2)
                
                print(f"{Fore.GREEN}✓ Exported pwnie {pwnie_id} to {filename}{Style.RESET_ALL}")
        
        except ValueError:
            print(f"{Fore.RED}Error: Invalid pwnie ID{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
    
    def do_filter(self, arg):
        """Filter and list pwnies by criteria
        Usage: filter <criteria>
        
        Criteria options:
          running          - Show only running pwnies
          stopped          - Show only stopped pwnies
          enrolled         - Show only enrolled pwnies
          tor              - Show only pwnies using Tor
          personality <X>  - Show pwnies with personality X
        
        Examples:
          filter running
          filter tor
          filter personality aggressive
        """
        parts = arg.split()
        
        if not parts:
            print(f"{Fore.RED}Error: Specify filter criteria{Style.RESET_ALL}")
            return
        
        pwnies = self.manager.list_all()
        filtered = []
        
        criteria = parts[0].lower()
        
        if criteria == 'running':
            filtered = [p for p in pwnies if p['running']]
        elif criteria == 'stopped':
            filtered = [p for p in pwnies if not p['running']]
        elif criteria == 'enrolled':
            filtered = [p for p in pwnies if p['enrolled']]
        elif criteria == 'tor':
            filtered = [p for p in pwnies if p['use_tor']]
        elif criteria == 'personality' and len(parts) > 1:
            target_pers = parts[1].lower()
            filtered = [p for p in pwnies if p['personality'].lower() == target_pers]
        else:
            print(f"{Fore.RED}Error: Unknown filter criteria{Style.RESET_ALL}")
            return
        
        if not filtered:
            print(f"{Fore.YELLOW}No pwnies match the filter{Style.RESET_ALL}")
            return
        
        # Print filtered results
        headers = ['ID', 'Name', 'Status', 'Enrolled', 'Pwned', 'Epoch', 'Tor', 'Version']
        rows = []
        
        for p in filtered:
            status_color = Fore.GREEN if p['running'] else Fore.RED
            status = f"{status_color}{'RUN' if p['running'] else 'OFF'}{Style.RESET_ALL}"
            enrolled = f"{Fore.GREEN}Yes{Style.RESET_ALL}" if p['enrolled'] else f"{Fore.RED}No{Style.RESET_ALL}"
            tor = f"{Fore.MAGENTA}Yes{Style.RESET_ALL}" if p['use_tor'] else "No"
            
            rows.append([
                p['id'],
                p['name'],
                status,
                enrolled,
                p['pwned'],
                p['epoch'],
                tor,
                p['version']
            ])
        
        print(f"\n{Fore.CYAN}Filtered Results ({len(filtered)} pwnies):{Style.RESET_ALL}\n")
        print(tabulate(rows, headers=headers, tablefmt='simple'))
    
    def do_batch(self, arg):
        """Perform batch operations on multiple pwnies
        Usage: batch <operation> <pwnie_ids>
        
        Operations: boot, shutdown, reboot, addnets
        
        Examples:
          batch boot 1 2 3           - Boot pwnies 1, 2, and 3
          batch shutdown 1-5         - Shutdown pwnies 1 through 5
          batch addnets:10 1 2       - Add 10 networks to pwnies 1 and 2
        """
        parts = arg.split()
        
        if len(parts) < 2:
            print(f"{Fore.RED}Error: Usage: batch <operation> <pwnie_ids>{Style.RESET_ALL}")
            return
        
        operation = parts[0].lower()
        pwnie_specs = parts[1:]
        
        # Parse pwnie IDs
        pwnie_ids = []
        for spec in pwnie_specs:
            if '-' in spec:
                # Range: 1-5
                try:
                    start, end = map(int, spec.split('-'))
                    pwnie_ids.extend(range(start, end + 1))
                except:
                    print(f"{Fore.RED}Error: Invalid range: {spec}{Style.RESET_ALL}")
                    return
            else:
                try:
                    pwnie_ids.append(int(spec))
                except:
                    print(f"{Fore.RED}Error: Invalid ID: {spec}{Style.RESET_ALL}")
                    return
        
        # Handle addnets special case
        count = None
        if ':' in operation:
            op_parts = operation.split(':')
            operation = op_parts[0]
            if operation == 'addnets':
                try:
                    count = int(op_parts[1])
                except:
                    print(f"{Fore.RED}Error: Invalid count for addnets{Style.RESET_ALL}")
                    return
        
        # Execute operation
        success_count = 0
        for pwnie_id in pwnie_ids:
            if pwnie_id not in self.manager.pwnies:
                print(f"{Fore.YELLOW}Skipping non-existent pwnie {pwnie_id}{Style.RESET_ALL}")
                continue
            
            if operation == 'boot':
                success, _ = self.manager.boot_pwnie(pwnie_id)
                if success:
                    success_count += 1
            elif operation == 'shutdown':
                success, _ = self.manager.shutdown_pwnie(pwnie_id)
                if success:
                    success_count += 1
            elif operation == 'reboot':
                success, _ = self.manager.reboot_pwnie(pwnie_id)
                if success:
                    success_count += 1
            elif operation == 'addnets' and count:
                success, _ = self.manager.add_pwned_networks(pwnie_id, count)
                if success:
                    success_count += 1
            else:
                print(f"{Fore.RED}Error: Unknown operation: {operation}{Style.RESET_ALL}")
                return
        
        print(f"{Fore.GREEN}✓ Operation completed on {success_count}/{len(pwnie_ids)} pwnies{Style.RESET_ALL}")
    
    def do_health(self, arg):
        """Check health status of all pwnies
        Usage: health
        
        Shows: unresponsive pwnies, enrollment issues, Tor failures, etc.
        """
        pwnies = self.manager.list_all()
        
        issues = {
            'not_enrolled': [],
            'tor_down': [],
            'low_activity': []
        }
        
        for p in pwnies:
            if not p['enrolled']:
                issues['not_enrolled'].append(p)
            
            if p['use_tor'] and p['running']:
                tor_info = self.manager.get_tor_info(p['id'])
                if tor_info and tor_info.get('status') != 'running':
                    issues['tor_down'].append(p)
            
            if p['running'] and p['epoch'] < 10:
                issues['low_activity'].append(p)
        
        print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Fleet Health Check{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        
        total_issues = sum(len(v) for v in issues.values())
        
        if total_issues == 0:
            print(f"{Fore.GREEN}✓ All pwnies healthy!{Style.RESET_ALL}")
        else:
            if issues['not_enrolled']:
                print(f"\n{Fore.YELLOW}⚠ Not Enrolled ({len(issues['not_enrolled'])}):{ Style.RESET_ALL}")
                for p in issues['not_enrolled']:
                    print(f"  - Pwnie {p['id']}: {p['name']}")
            
            if issues['tor_down']:
                print(f"\n{Fore.RED}✗ Tor Issues ({len(issues['tor_down'])}):{ Style.RESET_ALL}")
                for p in issues['tor_down']:
                    print(f"  - Pwnie {p['id']}: {p['name']}")
            
            if issues['low_activity']:
                print(f"\n{Fore.YELLOW}⚠ Low Activity ({len(issues['low_activity'])}):{ Style.RESET_ALL}")
                for p in issues['low_activity']:
                    print(f"  - Pwnie {p['id']}: {p['name']} (epoch: {p['epoch']})")
    
    def do_clear(self, arg):
        """Clear the terminal screen
        Usage: clear
        """
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def do_theme(self, arg):
        """Change color theme
        Usage: theme [name]
        
        Available themes: default, matrix, ocean, fire, mono
        
        Examples:
          theme              - Show current theme and available themes
          theme matrix       - Switch to matrix theme
        """
        global ACTIVE_THEME
        
        if not arg:
            # Show current theme and available
            print(f"\n{get_color('primary')}Current theme: {get_color('highlight')}{ACTIVE_THEME}{Style.RESET_ALL}")
            print(f"\n{get_color('info')}Available themes:{Style.RESET_ALL}")
            
            for theme_name, colors in COLOR_THEMES.items():
                current = " (current)" if theme_name == ACTIVE_THEME else ""
                print(f"  {colors['primary']}• {theme_name}{Style.RESET_ALL}{current}")
                print(f"    Example: {colors['success']}Success{Style.RESET_ALL} | "
                      f"{colors['warning']}Warning{Style.RESET_ALL} | "
                      f"{colors['error']}Error{Style.RESET_ALL} | "
                      f"{colors['highlight']}Highlight{Style.RESET_ALL}")
            
            return
        
        theme_name = arg.lower().strip()
        
        if theme_name not in COLOR_THEMES:
            print(f"{get_color('error')}Error: Unknown theme '{theme_name}'{Style.RESET_ALL}")
            print(f"{get_color('info')}Available: {', '.join(COLOR_THEMES.keys())}{Style.RESET_ALL}")
            return
        
        # Update theme
        ACTIVE_THEME = theme_name
        self.config.set('theme', theme_name)
        
        # Update prompt
        self.prompt = f'{get_color("success")}pwnie-fleet> {Style.RESET_ALL}'
        
        print(f"{get_color('success')}✓ Theme changed to: {get_color('highlight')}{theme_name}{Style.RESET_ALL}")
        print(f"{get_color('info')}Restart for full effect on all UI elements{Style.RESET_ALL}")
    
    def do_config(self, arg):
        """View or modify configuration
        Usage: config [key] [value]
        
        Examples:
          config                    - Show all configuration
          config theme matrix       - Set theme to matrix
          config update_interval 5  - Set update interval to 5 seconds
        """
        global ACTIVE_THEME
        
        if not arg:
            # Show all config
            print(f"\n{get_color('primary')}Current Configuration:{Style.RESET_ALL}\n")
            
            for key, value in self.config.config.items():
                print(f"  {get_color('info')}{key:20}{Style.RESET_ALL}: {get_color('highlight')}{value}{Style.RESET_ALL}")
            
            print(f"\n{get_color('info')}💡 Use 'config <key> <value>' to modify{Style.RESET_ALL}")
            return
        
        parts = arg.split(maxsplit=1)
        
        if len(parts) == 1:
            # Show specific key
            key = parts[0]
            value = self.config.get(key)
            if value is not None:
                print(f"{get_color('info')}{key}{Style.RESET_ALL}: {get_color('highlight')}{value}{Style.RESET_ALL}")
            else:
                print(f"{get_color('error')}Error: Unknown configuration key '{key}'{Style.RESET_ALL}")
        else:
            # Set value
            key, value = parts
            
            # Try to parse value as appropriate type
            if value.lower() == 'true':
                value = True
            elif value.lower() == 'false':
                value = False
            elif value.isdigit():
                value = int(value)
            
            self.config.set(key, value)
            
            # Apply specific changes
            if key == 'theme':
                ACTIVE_THEME = value
                self.prompt = f'{get_color("success")}pwnie-fleet> {Style.RESET_ALL}'
            
            print(f"{get_color('success')}✓ Set {key} = {value}{Style.RESET_ALL}")
    
    def do_save(self, arg):
        """Save all pwnies' state to disk
        Usage: save
        """
        print(f"{Fore.YELLOW}Saving all pwnies...{Style.RESET_ALL}")
        self.manager.save_all()
        print(f"{Fore.GREEN}All pwnies saved{Style.RESET_ALL}")
    
    def do_cleanup(self, arg):
        """Remove old/incompatible pwnie files from disk
        Usage: cleanup
        """
        if not self.manager.pwnies_dir.exists():
            print(f"{Fore.YELLOW}No pwnies directory found{Style.RESET_ALL}")
            return
        
        old_files = []
        
        # Find old format JSON files (missing public_key)
        for pwnie_file in self.manager.pwnies_dir.glob("*.json"):
            try:
                with open(pwnie_file, 'r') as f:
                    data = json.load(f)
                    if 'public_key' not in data:
                        old_files.append(pwnie_file)
            except:
                old_files.append(pwnie_file)
        
        if not old_files:
            print(f"{Fore.GREEN}No old files found - all clean!{Style.RESET_ALL}")
            return
        
        print(f"{Fore.YELLOW}Found {len(old_files)} old/incompatible files:{Style.RESET_ALL}")
        for f in old_files[:10]:  # Show first 10
            print(f"  - {f.name}")
        if len(old_files) > 10:
            print(f"  ... and {len(old_files) - 10} more")
        
        confirm = input(f"\n{Fore.RED}Delete all {len(old_files)} files? (yes/no): {Style.RESET_ALL}")
        
        if confirm.lower() == 'yes':
            for f in old_files:
                # Also try to delete associated PEM file
                pem_file = f.with_suffix('.pem')
                if pem_file.exists():
                    pem_file.unlink()
                # Delete JSON
                f.unlink()
            print(f"{Fore.GREEN}Deleted {len(old_files)} old files{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}Cleanup cancelled{Style.RESET_ALL}")
    
    def do_convert(self, arg):
        """Convert old format pwnie files to new format
        Usage: convert <pwnie_name>
               convert all
        
        This will convert old generator format files to the fleet manager format,
        preserving all stats and data.
        """
        if not arg:
            print(f"{Fore.RED}Error: Specify a pwnie name or 'all'{Style.RESET_ALL}")
            print("Usage: convert <pwnie_name>  OR  convert all")
            return
        
        if not self.manager.pwnies_dir.exists():
            print(f"{Fore.YELLOW}No pwnies directory found{Style.RESET_ALL}")
            return
        
        # Find old format files
        old_files = []
        for pwnie_file in self.manager.pwnies_dir.glob("*.json"):
            try:
                with open(pwnie_file, 'r') as f:
                    data = json.load(f)
                    if 'public_key' not in data:
                        old_files.append((pwnie_file, data))
            except:
                continue
        
        if not old_files:
            print(f"{Fore.GREEN}No old format files found - all up to date!{Style.RESET_ALL}")
            return
        
        # Filter by name if not 'all'
        if arg.lower() != 'all':
            old_files = [(f, d) for f, d in old_files if d.get('name') == arg]
            if not old_files:
                print(f"{Fore.RED}Pwnie '{arg}' not found or already in new format{Style.RESET_ALL}")
                return
        
        print(f"{Fore.CYAN}Converting {len(old_files)} pwnie(s) to new format...{Style.RESET_ALL}\n")
        
        converted = 0
        for pwnie_file, old_data in old_files:
            try:
                # Load private key if it exists
                key_file = self.manager.pwnies_dir / f"{old_data['name']}_private.pem"
                if not key_file.exists():
                    print(f"{Fore.RED}  ✗ {old_data['name']}: Missing private key file{Style.RESET_ALL}")
                    continue
                
                with open(key_file, 'rb') as f:
                    from Crypto.PublicKey import RSA
                    private_key = RSA.import_key(f.read())
                
                # Generate public key in PEM format
                public_key_pem = private_key.publickey().export_key('PEM').decode('utf-8')
                
                # Create new format data
                new_data = {
                    'id': old_data.get('id', 0),
                    'name': old_data['name'],
                    'fingerprint': old_data['fingerprint'],
                    'public_key': public_key_pem,  # Add missing field
                    'enrolled': old_data.get('enrolled', False),
                    'token': old_data.get('token', ''),
                    'pwnd_tot': old_data.get('pwnd_tot', 0),
                    'pwnd_run': old_data.get('pwnd_run', 0),
                    'epoch': old_data.get('epoch', 0),
                    'uptime': old_data.get('uptime', 0),
                    'version': old_data.get('version', '1.5.5'),
                    'personality': old_data.get('personality', 'balanced'),
                    'use_tor': old_data.get('use_tor', False),
                    'tor_port': old_data.get('tor_port'),
                    'session_data': old_data.get('session_data', {
                        'deauthed': 0,
                        'associated': 0,
                        'handshakes': 0,
                        'peers': 0,
                    }),
                    'access_points': old_data.get('access_points', []),
                }
                
                # Save updated file
                with open(pwnie_file, 'w') as f:
                    json.dump(new_data, f, indent=2)
                
                print(f"{Fore.GREEN}  ✓ {old_data['name']}: Converted (pwned: {old_data.get('pwnd_tot', 0)}){Style.RESET_ALL}")
                converted += 1
                
            except Exception as e:
                print(f"{Fore.RED}  ✗ {old_data.get('name', 'unknown')}: {str(e)}{Style.RESET_ALL}")
        
        print(f"\n{Fore.GREEN}Converted {converted}/{len(old_files)} pwnies{Style.RESET_ALL}")
        
        if converted > 0:
            print(f"{Fore.CYAN}Reload pwnies with: {Style.BRIGHT}reload{Style.RESET_ALL}")
    
    def do_create(self, arg):
        """Create new pwnies using the generator
        Usage: create [count] [--tor] [--pwned <number|random>]
        
        Examples:
          create              - Create 1 pwnie
          create 5            - Create 5 pwnies
          create 3 --tor      - Create 3 pwnies with Tor
          create 10 --pwned random  - Create 10 with random pwned counts
          create 1 --pwned 1000     - Create 1 with 1000 pwned networks
        """
        # Parse arguments
        args = arg.split()
        count = 1
        use_tor = False
        pwned = 'random'
        
        i = 0
        while i < len(args):
            if args[i] == '--tor':
                use_tor = True
            elif args[i] == '--pwned' and i + 1 < len(args):
                pwned = args[i + 1]
                i += 1
            elif args[i].isdigit():
                count = int(args[i])
            i += 1
        
        print(f"{Fore.CYAN}Creating {count} new pwnie(s)...{Style.RESET_ALL}")
        if use_tor:
            print(f"{Fore.YELLOW}Using Tor for each pwnie{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Initial pwned count: {pwned}{Style.RESET_ALL}\n")
        
        # Build command
        cmd = [
            sys.executable,
            'pwnagotchi-gen.py',
            '--count', str(count),
            '--pwned', pwned,
            '--yes'  # Skip confirmation prompt for automation
        ]
        
        if use_tor:
            cmd.append('--tor')
        
        # Run generator for 30 seconds
        print(f"{Fore.YELLOW}Running generator for 30 seconds to initialize...{Style.RESET_ALL}")
        
        try:
            import subprocess
            process = subprocess.Popen(cmd)
            time.sleep(30)
            process.terminate()
            process.wait(timeout=5)
            
            print(f"\n{Fore.GREEN}Pwnies created! Use 'reload' to load them.{Style.RESET_ALL}")
            
        except Exception as e:
            print(f"{Fore.RED}Error creating pwnies: {e}{Style.RESET_ALL}")
    
    def do_reload(self, arg):
        """Reload all pwnies from disk
        Usage: reload
        
        This will reload all pwnie files, picking up any new or converted pwnies.
        """
        print(f"{Fore.YELLOW}Reloading pwnies from disk...{Style.RESET_ALL}")
        
        # Stop all running pwnies first
        running = [p for p in self.manager.list_all() if p['running']]
        if running:
            print(f"{Fore.YELLOW}Stopping {len(running)} running pwnie(s) first...{Style.RESET_ALL}")
            for p in running:
                self.manager.shutdown(p['id'])
        
        # Clear and reload
        self.manager.pwnies.clear()
        self.manager.load_pwnies()
        
        count = len(self.manager.pwnies)
        print(f"{Fore.GREEN}Reloaded {count} pwnie(s){Style.RESET_ALL}")
    
    def do_listold(self, arg):
        """List pwnies in old format that need conversion
        Usage: listold
        """
        if not self.manager.pwnies_dir.exists():
            print(f"{Fore.YELLOW}No pwnies directory found{Style.RESET_ALL}")
            return
        
        old_files = []
        for pwnie_file in self.manager.pwnies_dir.glob("*.json"):
            try:
                with open(pwnie_file, 'r') as f:
                    data = json.load(f)
                    if 'public_key' not in data:
                        old_files.append(data)
            except:
                continue
        
        if not old_files:
            print(f"{Fore.GREEN}No old format files found - all up to date!{Style.RESET_ALL}")
            return
        
        print(f"\n{Fore.CYAN}Old Format Pwnies (need conversion):{Style.RESET_ALL}\n")
        
        headers = ['Name', 'Fingerprint', 'Pwned', 'Enrolled', 'Tor']
        rows = []
        
        for data in old_files:
            rows.append([
                data.get('name', 'unknown'),
                data.get('fingerprint', 'N/A')[:16] + '...',
                data.get('pwnd_tot', 0),
                '✓' if data.get('enrolled') else '✗',
                '✓' if data.get('use_tor') else '✗',
            ])
        
        print(tabulate(rows, headers=headers, tablefmt='simple'))
        print(f"\n{Fore.YELLOW}Total: {len(old_files)} old format file(s){Style.RESET_ALL}")
        print(f"\n{Fore.CYAN}⚠️  NOTE: Old files are missing private keys and stats!{Style.RESET_ALL}")
        print(f"{Fore.CYAN}   The old generator didn't save keys or pwned counts properly.{Style.RESET_ALL}")
        print(f"\n{Fore.YELLOW}Options:{Style.RESET_ALL}")
        print(f"  1. Create new pwnies: {Fore.BRIGHT}create 1 --pwned 1000{Style.RESET_ALL}")
        print(f"  2. Remove old files:  {Fore.BRIGHT}cleanup{Style.RESET_ALL}")
        print(f"  3. Try conversion:    {Fore.BRIGHT}convert <name>{Style.RESET_ALL} (will fail without keys)")
    
    def do_stats(self, arg):
        """Show aggregate statistics for all pwnies
        Usage: stats
        """
        pwnies = self.manager.list_all()
        
        if not pwnies:
            print(f"{Fore.YELLOW}No pwnies found{Style.RESET_ALL}")
            return
        
        total = len(pwnies)
        running = sum(1 for p in pwnies if p['running'])
        enrolled = sum(1 for p in pwnies if p['enrolled'])
        total_pwned = sum(p['pwned'] for p in pwnies)
        total_handshakes = sum(p['handshakes'] for p in pwnies)
        total_deauths = sum(p['deauths'] for p in pwnies)
        with_tor = sum(1 for p in pwnies if p['use_tor'])
        
        print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Fleet Statistics{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"Total Pwnies:      {total}")
        print(f"Running:           {Fore.GREEN}{running}{Style.RESET_ALL}")
        print(f"Stopped:           {Fore.RED}{total - running}{Style.RESET_ALL}")
        print(f"Enrolled:          {enrolled}")
        print(f"Using Tor:         {with_tor}")
        print(f"\n{Fore.YELLOW}Aggregate Stats:{Style.RESET_ALL}")
        print(f"Total Networks:    {total_pwned}")
        print(f"Total Handshakes:  {total_handshakes}")
        print(f"Total Deauths:     {total_deauths}")
        print(f"Avg Networks:      {total_pwned / total if total > 0 else 0:.1f}")
    
    def do_monitor(self, arg):
        """Monitor all running pwnies in real-time
        Usage: monitor [interval_seconds]
        """
        interval = 5
        if arg:
            try:
                interval = int(arg)
            except ValueError:
                print(f"{Fore.RED}Error: Invalid interval{Style.RESET_ALL}")
                return
        
        print(f"{Fore.CYAN}Monitoring mode (Ctrl+C to stop, interval: {interval}s){Style.RESET_ALL}\n")
        
        try:
            while True:
                os.system('cls' if os.name == 'nt' else 'clear')
                
                # Show stats
                self.do_stats('')
                print(f"\n{Fore.CYAN}Running Pwnies:{Style.RESET_ALL}")
                
                # Show running pwnies
                pwnies = self.manager.list_all()
                running_pwnies = [p for p in pwnies if p['running']]
                
                if running_pwnies:
                    headers = ['ID', 'Name', 'Pwned', 'HS', 'Deauth', 'Epoch', 'Uptime']
                    rows = []
                    
                    for p in running_pwnies:
                        rows.append([
                            p['id'],
                            p['name'],
                            p['pwned'],
                            p['handshakes'],
                            p['deauths'],
                            p['epoch'],
                            f"{p['uptime']}s",
                        ])
                    
                    print(tabulate(rows, headers=headers, tablefmt='simple'))
                else:
                    print(f"{Fore.YELLOW}No pwnies currently running{Style.RESET_ALL}")
                
                print(f"\n{Fore.CYAN}Next update in {interval}s...{Style.RESET_ALL}")
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Monitoring stopped{Style.RESET_ALL}")
    
    def do_exit(self, arg):
        """Exit the manager
        Usage: exit
        """
        print(f"{Fore.YELLOW}Saving state and exiting...{Style.RESET_ALL}")
        self.manager.save_all()
        print(f"{Fore.GREEN}Goodbye!{Style.RESET_ALL}")
        return True
    
    def do_quit(self, arg):
        """Exit the manager
        Usage: quit
        """
        return self.do_exit(arg)
    
    def do_EOF(self, arg):
        """Exit on Ctrl+D"""
        print()
        return self.do_exit(arg)


def main():
    parser = argparse.ArgumentParser(
        description='Pwnagotchi Fleet Manager - Interactive Management Console'
    )
    parser.add_argument('--pwnies-dir', default=PWNIES_DIR,
                       help=f'Directory containing pwnie data (default: {PWNIES_DIR})')
    parser.add_argument('--webui', action='store_true',
                       help='Start web UI dashboard')
    parser.add_argument('--host', default='0.0.0.0',
                       help='Web UI host (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=5000,
                       help='Web UI port (default: 5000)')
    parser.add_argument('--tmux', action='store_true',
                       help='Launch in tmux with split panes')
    parser.add_argument('--force-tor', action='store_true',
                       help='Enable Tor for all pwnies at startup')
    parser.add_argument('--theme', default=None,
                       help='Set color theme (default, matrix, ocean, fire, mono)')
    
    args = parser.parse_args()
    
    # Handle tmux launch
    if args.tmux:
        launch_script = Path(__file__).parent / 'launch-tmux.sh'
        if launch_script.exists():
            print(f"{Fore.CYAN}Launching Fleet Manager in tmux...{Style.RESET_ALL}")
            subprocess.run(['bash', str(launch_script)])
            sys.exit(0)
        else:
            print(f"{Fore.RED}Error: launch-tmux.sh not found{Style.RESET_ALL}")
            sys.exit(1)
    
    # Load configuration
    config = FleetConfig()
    
    # Apply theme override from command line
    if args.theme:
        if args.theme in COLOR_THEMES:
            config.set('theme', args.theme)
            global ACTIVE_THEME
            ACTIVE_THEME = args.theme
        else:
            print(f"{Fore.YELLOW}Warning: Unknown theme '{args.theme}', using default{Style.RESET_ALL}")
    
    # Create manager
    manager = PwnieManager(pwnies_dir=args.pwnies_dir)
    
    # Handle --force-tor flag
    if args.force_tor:
        print(f"{get_color('primary')}Enabling Tor for all pwnies...{Style.RESET_ALL}")
        enabled_count = 0
        for pwnie_id in manager.pwnies.keys():
            pwnie = manager.pwnies[pwnie_id]
            if not pwnie.get('tor_enabled', False):
                manager.toggle_tor(pwnie_id, enable=True)
                enabled_count += 1
        
        if enabled_count > 0:
            print(f"{get_color('success')}✓ Enabled Tor for {enabled_count} pwnie(s){Style.RESET_ALL}")
        else:
            print(f"{get_color('info')}All pwnies already have Tor enabled{Style.RESET_ALL}")
    
    if args.webui:
        # Start web UI
        try:
            from pwnie_webui import start_webui
            print(f"{get_color('primary')}Starting Web UI Dashboard...{Style.RESET_ALL}")
            start_webui(manager, host=args.host, port=args.port)
        except ImportError as e:
            print(f"{get_color('error')}Error: Web UI dependencies not installed{Style.RESET_ALL}")
            print(f"Install with: pip install flask flask-socketio")
            print(f"Error details: {e}")
            sys.exit(1)
    else:
        # Start CLI
        cli = PwnieManagerCLI(manager, config=config)
        
        try:
            cli.cmdloop()
        except KeyboardInterrupt:
            print(f"\n{get_color('warning')}Interrupted. Saving and exiting...{Style.RESET_ALL}")
            manager.save_all()


if __name__ == "__main__":
    main()

