#!/usr/bin/env python3
"""
Pwnagotchi Grid Test Generator
Generates synthetic Pwnagotchi instances for testing with the official opwngrid.xyz

How it works:
1. Each fake unit generates an RSA keypair and fingerprint
2. Units enroll with opwngrid via POST /api/v1/unit/enroll with:
   - identity (name@fingerprint)
   - public_key (base64 PEM)
   - signature (signed identity)
   - data (unit stats and session info)
3. Enrollment returns a JWT token
4. Units periodically re-enroll to update their data (opwngrid uses enrollment for updates)
5. Stats (handshakes, epochs, etc.) are randomly incremented to simulate activity
6. Each unit can use its own Tor circuit for anonymity

Based on the actual Pwnagotchi and pwngrid source code.
"""

import os
import sys
import json
import time
import random
import hashlib
import base64
import requests
import threading
import argparse
import subprocess
from datetime import datetime
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_PSS
import Crypto.Hash.SHA256 as SHA256

# Configuration
OPWNGRID_API_URL = "https://your.opwngrid-api-url.com/api/v1"  # Your opwngrid API URL
NUM_PWNIES = 10  # Number of fake pwnagotchis to generate
UPDATE_INTERVAL = 60  # Seconds between updates (increased to avoid spam)
OUTPUT_DIR = "./fake_pwnies"
USE_TOR = False  # Use Tor for anonymity
TOR_SOCKS_PORT_START = 9050  # Starting port for Tor SOCKS proxies
CUSTOM_PWNED_COUNT = None  # Set specific pwned count, or None for random

# Pwnagotchi name pool for random generation
NAME_PREFIXES = ["pwn", "hack", "wifi", "net", "byte", "bit", "cyber", "ghost", "phantom", "ninja"]
NAME_SUFFIXES = ["hunter", "snatcher", "grabber", "catcher", "seeker", "finder", "master", "warrior", "daemon", "bot"]

# Pwnagotchi faces - randomly selected
FACES = [
    "(◕‿◕)", "(⌐■_■)", "(ಠ_ಠ)", "(◕‿◕✿)", "(｡◕‿◕｡)",
    "( ͡° ͜ʖ ͡°)", "(づ｡◕‿‿◕｡)づ", "ヽ(°◇° )ノ", "(｡♥‿♥｡)",
    "(>ᴗ<)", "(≧◡≦)", "♥‿♥", "(✿◠‿◠)", "◕‿↼",
    "(ʘ‿ʘ)", "¯\\_(ツ)_/¯", "(☞ﾟヮﾟ)☞", "☜(ﾟヮﾟ☜)", "(¬‿¬)",
    "(◔_◔)", "(•‿•)", "(⊙_⊙)", "(҂◡_◡)", "ᕕ( ᐛ )ᕗ"
]

# Personality presets
PERSONALITIES = {
    "aggressive": {
        "advertise": True,
        "deauth": True,
        "associate": True,
        "channels": [],
        "min_rssi": -200,
        "ap_ttl": 120,
        "sta_ttl": 300,
        "recon_time": 30,
        "hop_recon_time": 10,
        "min_recon_time": 5,
        "max_interactions": 5,
    },
    "passive": {
        "advertise": True,
        "deauth": False,
        "associate": True,
        "channels": [],
        "min_rssi": -150,
        "ap_ttl": 180,
        "sta_ttl": 400,
        "recon_time": 45,
        "hop_recon_time": 15,
        "min_recon_time": 8,
        "max_interactions": 2,
    },
    "balanced": {
        "advertise": True,
        "deauth": True,
        "associate": True,
        "channels": [],
        "min_rssi": -180,
        "ap_ttl": 120,
        "sta_ttl": 300,
        "recon_time": 30,
        "hop_recon_time": 10,
        "min_recon_time": 5,
        "max_interactions": 3,
    }
}


class FakePwnagotchi:
    """Simulates a Pwnagotchi device"""
    
    def __init__(self, pwny_id, opwngrid_url, use_tor=False, tor_port=None, custom_pwned=None, custom_name=None, report_threads=1):
        self.pwny_id = pwny_id
        self.opwngrid_url = opwngrid_url
        self.running = False
        self.paused = False  # Track if unit is temporarily paused
        self.token = None  # Enrollment token
        self.use_tor = use_tor
        self.tor_port = tor_port
        self.tor_process = None
        self.tor_dir = None  # Will be set in _setup_tor
        self.custom_pwned = custom_pwned
        self.custom_name = custom_name
        self.report_threads = report_threads
        
        # Error tracking
        self.consecutive_errors = 0
        self.max_consecutive_errors = 5
        
        # Setup Tor if requested
        if self.use_tor:
            self._setup_tor()
        
        # Generate identity
        self.name = self._generate_name()
        self.keypair = self._generate_keypair()
        self.fingerprint = self.keypair['fingerprint']
        self.identity = f"{self.name}@{self.fingerprint}"
        self.face = random.choice(FACES)  # Random face
        
        # Initialize stats with custom pwned count if specified
        self.start_time = time.time()
        self.epoch = 0
        if custom_pwned is not None:
            self.pwnd_run = custom_pwned
            self.pwnd_tot = custom_pwned
        else:
            # Random starting handshakes (0-100)
            initial_pwned = random.randint(0, 100)
            self.pwnd_run = initial_pwned
            self.pwnd_tot = initial_pwned
        self.personality = random.choice(list(PERSONALITIES.keys()))
        
        # Session data
        self.session_data = {
            'duration': 0,
            'epochs': 0,
            'train_epochs': 0,
            'avg_reward': 0.0,
            'min_reward': -100.0,
            'max_reward': 100.0,
            'deauthed': 0,
            'associated': 0,
            'handshakes': 0,
            'peers': 0,
        }
        
        print(f"[{self.name}] Created with fingerprint: {self.fingerprint[:16]}... | Face: {self.face} | Pwned: {self.pwnd_tot}{' | Tor: ' + str(self.tor_port) if self.use_tor else ''}")
    
    def _setup_tor(self):
        """Setup a Tor SOCKS proxy for this unit"""
        try:
            # Check if tor is installed
            tor_check = subprocess.run(['tor', '--version'], 
                                     capture_output=True, 
                                     text=True, 
                                     timeout=5)
            if tor_check.returncode != 0:
                print(f"[{self.pwny_id}] Tor not found, will connect without Tor")
                self.use_tor = False
                return
            
            # Create a temporary torrc file for this instance
            self.tor_dir = os.path.join(OUTPUT_DIR, f"tor_{self.pwny_id}")
            os.makedirs(self.tor_dir, exist_ok=True)
            
            torrc_path = os.path.join(self.tor_dir, "torrc")
            with open(torrc_path, 'w') as f:
                f.write(f"SocksPort {self.tor_port}\n")
                f.write(f"DataDirectory {self.tor_dir}/data\n")
                f.write("ControlPort 0\n")  # Disable control port
            
            # Start Tor process
            self.tor_process = subprocess.Popen(
                ['tor', '-f', torrc_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Wait for Tor to be ready
            print(f"[{self.pwny_id}] Starting Tor on port {self.tor_port}...")
            time.sleep(5)  # Give Tor time to establish circuits
            
            print(f"[{self.pwny_id}] ✓ Tor circuit established on port {self.tor_port}")
            
        except Exception as e:
            print(f"[{self.pwny_id}] Failed to setup Tor: {e}, will connect without Tor")
            self.use_tor = False
            if self.tor_process:
                self.tor_process.terminate()
                self.tor_process = None
    
    def _rotate_tor_circuit(self):
        """Rotate to a new Tor circuit by restarting Tor"""
        if not self.use_tor or not self.tor_process:
            return False
        
        try:
            print(f"[{self.name}] 🔄 Rotating Tor circuit...")
            
            # Terminate old Tor process
            self.tor_process.terminate()
            try:
                self.tor_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.tor_process.kill()
            
            # Clean up old data directory to force new identity
            data_dir = os.path.join(self.tor_dir, "data")
            if os.path.exists(data_dir):
                import shutil
                shutil.rmtree(data_dir, ignore_errors=True)
            
            # Restart Tor with same config
            torrc_path = os.path.join(self.tor_dir, "torrc")
            self.tor_process = subprocess.Popen(
                ['tor', '-f', torrc_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Wait for new circuit
            print(f"[{self.name}] ⏳ Waiting for new Tor circuit...")
            time.sleep(7)  # Slightly longer wait for fresh circuit
            
            print(f"[{self.name}] ✓ New Tor circuit established")
            return True
            
        except Exception as e:
            print(f"[{self.name}] ❌ Failed to rotate Tor circuit: {e}")
            return False
    
    def _generate_name(self):
        """Generate a random pwnagotchi name or use custom name if provided"""
        if self.custom_name:
            return self.custom_name
        prefix = random.choice(NAME_PREFIXES)
        suffix = random.choice(NAME_SUFFIXES)
        num = random.randint(1, 999)
        return f"{prefix}{suffix}{num}"
    
    def _generate_keypair(self):
        """Generate RSA keypair like the real Pwnagotchi"""
        key = RSA.generate(2048)
        priv_key = key.export_key('PEM').decode('ascii')
        pub_key = key.publickey().export_key('PEM').decode('ascii')
        
        # Ensure RSA PUBLIC KEY format
        if 'RSA PUBLIC KEY' not in pub_key:
            pub_key = pub_key.replace('PUBLIC KEY', 'RSA PUBLIC KEY')
        
        pub_key_pem_b64 = base64.b64encode(pub_key.encode('ascii')).decode('ascii')
        fingerprint = hashlib.sha256(pub_key.encode('ascii')).hexdigest()
        
        return {
            'private_obj': key,  # RSA key object for signing
            'private': priv_key,  # PEM string for saving
            'public': pub_key,
            'public_b64': pub_key_pem_b64,
            'fingerprint': fingerprint
        }
    
    def _sign_message(self, message):
        """Sign a message with the private key"""
        hasher = SHA256.new(message.encode('ascii') if isinstance(message, str) else message)
        signer = PKCS1_PSS.new(self.keypair['private_obj'], saltLen=16)
        signature = signer.sign(hasher)
        return signature
    
    def enroll(self, retry_count=0, max_retries=3):
        """Enroll/update this unit with the opwngrid server"""
        try:
            # Create signature of identity
            signature = self._sign_message(self.identity)
            signature_b64 = base64.b64encode(signature).decode('ascii')
            
            # Build enrollment data with current stats
            enrollment = {
                'identity': self.identity,
                'public_key': self.keypair['public_b64'],
                'signature': signature_b64,
                'data': {
                    'name': self.name,
                    'version': '2.9.5.3',
                    'ai': 'No AI!',
                    'advertisement': self._get_advertisement_data(),
                    'session': self.session_data,
                    'uname': 'Linux 6.6.62+rpt-rpi-v8 #1 SMP PREEMPT Debian 1:6.6.62-1+rpt1 (2024-11-25) aarch64 GNU/Linux',
                    'build': 'Pwnagotchi by Jayofelony',
                    'plugins': ['grid', 'auto-update', 'webcfg'],
                    'language': 'en',
                    'bettercap': 'bettercap v2.32.0',
                    'opwngrid': 'pwngrid v1.10.3'
                }
            }
            
            url = f"{self.opwngrid_url}/unit/enroll"
            
            # Setup session with or without Tor
            session = requests.Session()
            if self.use_tor and self.tor_port:
                session.proxies = {
                    'http': f'socks5h://127.0.0.1:{self.tor_port}',
                    'https': f'socks5h://127.0.0.1:{self.tor_port}'
                }
            
            r = session.post(url, json=enrollment, timeout=30)
            
            # Check for rate limiting or blocking
            if r.status_code == 429:  # Too Many Requests
                print(f"[{self.name}] ⚠️  Rate limited (429)")
                if self.use_tor and retry_count < max_retries:
                    if self._rotate_tor_circuit():
                        time.sleep(2)
                        return self.enroll(retry_count + 1, max_retries)
                return False
            
            elif r.status_code == 403:  # Forbidden
                print(f"[{self.name}] ⚠️  Blocked (403)")
                if self.use_tor and retry_count < max_retries:
                    if self._rotate_tor_circuit():
                        time.sleep(2)
                        return self.enroll(retry_count + 1, max_retries)
                return False
            
            elif r.status_code == 503:  # Service Unavailable
                print(f"[{self.name}] ⚠️  Service unavailable (503), retrying...")
                if retry_count < max_retries:
                    time.sleep(5)
                    return self.enroll(retry_count + 1, max_retries)
                return False
            
            elif r.status_code == 200:
                result = r.json()
                self.token = result.get('token')
                self.consecutive_errors = 0  # Reset error counter on success
                if self.epoch == 0:
                    print(f"[{self.name}] ✓ Enrolled successfully")
                else:
                    print(f"[{self.name}] ✓ Updated - Epoch: {self.epoch}, Handshakes: {self.pwnd_tot}")
                return True
            else:
                self.consecutive_errors += 1
                print(f"[{self.name}] Enrollment failed: {r.status_code} - {r.text[:100]}")
                return False
                
        except requests.exceptions.ProxyError as e:
            self.consecutive_errors += 1
            print(f"[{self.name}] ⚠️  Tor proxy error")
            if self.use_tor and retry_count < max_retries:
                if self._rotate_tor_circuit():
                    return self.enroll(retry_count + 1, max_retries)
            return False
            
        except requests.exceptions.Timeout:
            self.consecutive_errors += 1
            print(f"[{self.name}] ⚠️  Request timeout")
            if retry_count < max_retries:
                time.sleep(3)
                return self.enroll(retry_count + 1, max_retries)
            return False
            
        except Exception as e:
            self.consecutive_errors += 1
            print(f"[{self.name}] Enrollment error: {e}")
            if retry_count < max_retries:
                time.sleep(2)
                return self.enroll(retry_count + 1, max_retries)
            return False
    
    def _generate_fake_ap(self):
        """Generate a fake access point ESSID and BSSID"""
        # Common WiFi ESSID patterns
        essid_patterns = [
            lambda: f"xfinitywifi",
            lambda: f"NETGEAR{random.randint(10, 99)}",
            lambda: f"TP-LINK_{random.choice(['2.4GHz', '5GHz'])}_{random.randint(1000, 9999)}",
            lambda: f"Linksys{random.randint(1000, 9999)}",
            lambda: f"ATT{random.randint(100, 999)}",
            lambda: f"HOME-{random.randint(1000, 9999)}",
            lambda: f"WiFi-{random.randint(100, 999)}",
            lambda: f"CenturyLink{random.randint(1000, 9999)}",
            lambda: f"Spectrum{random.choice(['2G', '5G'])}-{random.randint(10, 99)}",
            lambda: f"Verizon_{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=4))}",
        ]
        
        essid = random.choice(essid_patterns)()
        
        # Generate random MAC address
        mac = ':'.join(['%02x' % random.randint(0, 255) for _ in range(6)])
        
        return essid, mac
    
    def report_ap(self, essid, bssid, retry_count=0, max_retries=3):
        """Report a pwned access point to the grid"""
        try:
            url = f"{self.opwngrid_url}/unit/report/ap"
            
            # Setup session with or without Tor
            session = requests.Session()
            if self.use_tor and self.tor_port:
                session.proxies = {
                    'http': f'socks5h://127.0.0.1:{self.tor_port}',
                    'https': f'socks5h://127.0.0.1:{self.tor_port}'
                }
            
            # Need to use token for authenticated requests
            headers = {'Authorization': f'Bearer {self.token}'} if self.token else {}
            
            data = {
                'essid': essid,
                'bssid': bssid
            }
            
            r = session.post(url, json=data, headers=headers, timeout=30)
            
            # Check for rate limiting or blocking
            if r.status_code == 429:  # Too Many Requests
                if retry_count == 0:  # Only log once
                    print(f"[{self.name}] ⚠️  Rate limited on AP report")
                if self.use_tor and retry_count < max_retries:
                    if self._rotate_tor_circuit():
                        time.sleep(2)
                        return self.report_ap(essid, bssid, retry_count + 1, max_retries)
                return False
            
            elif r.status_code == 403:  # Forbidden
                if retry_count == 0:
                    print(f"[{self.name}] ⚠️  Blocked on AP report")
                if self.use_tor and retry_count < max_retries:
                    if self._rotate_tor_circuit():
                        time.sleep(2)
                        return self.report_ap(essid, bssid, retry_count + 1, max_retries)
                return False
            
            elif r.status_code == 503:  # Service Unavailable
                if retry_count < max_retries:
                    time.sleep(3)
                    return self.report_ap(essid, bssid, retry_count + 1, max_retries)
                return False
            
            elif r.status_code == 200:
                if retry_count == 0:  # Normal report
                    print(f"[{self.name}] ✓ Reported AP: {essid} ({bssid})")
                else:  # Successful retry
                    print(f"[{self.name}] ✓ Reported AP after retry: {essid}")
                return True
            else:
                if retry_count == 0:
                    print(f"[{self.name}] Failed to report AP: {r.status_code}")
                return False
                
        except requests.exceptions.ProxyError:
            if self.use_tor and retry_count < max_retries:
                if self._rotate_tor_circuit():
                    return self.report_ap(essid, bssid, retry_count + 1, max_retries)
            return False
            
        except requests.exceptions.Timeout:
            if retry_count < max_retries:
                time.sleep(2)
                return self.report_ap(essid, bssid, retry_count + 1, max_retries)
            return False
            
        except Exception as e:
            if retry_count == 0:
                print(f"[{self.name}] Error reporting AP: {e}")
            return False
    
    def _update_stats(self):
        """Update statistics to simulate real activity"""
        # Simulate activity
        self.epoch += 1
        
        # Randomly add handshakes (0-3 per update)
        new_handshakes = random.randint(0, 3) if random.random() > 0.5 else 0
        
        # Report new access points for the handshakes
        for _ in range(new_handshakes):
            essid, bssid = self._generate_fake_ap()
            # Report with a small delay to avoid overwhelming the server
            if self.token:  # Only report if we have a valid token
                self.report_ap(essid, bssid)
                time.sleep(0.5)  # Small delay between reports
        
        self.pwnd_run += new_handshakes
        self.pwnd_tot += new_handshakes
        
        # Update session data
        self.session_data['epochs'] = self.epoch
        self.session_data['duration'] = int(time.time() - self.start_time)
        self.session_data['deauthed'] += random.randint(0, 10)
        self.session_data['associated'] += random.randint(0, 5)
        self.session_data['handshakes'] = self.pwnd_tot  # Use total, not just run
        self.session_data['peers'] = random.randint(0, 3)
        self.session_data['avg_reward'] = random.uniform(-50, 150)
        self.session_data['min_reward'] = random.uniform(-200, -50)
        self.session_data['max_reward'] = random.uniform(100, 300)
    
    def _get_advertisement_data(self):
        """Get advertisement data like real Pwnagotchi"""
        return {
            'name': self.name,
            'version': '2.8.9',  # Current version
            'identity': self.fingerprint,
            'face': self.face,  # Use the random face
            'pwnd_run': self.pwnd_run,
            'pwnd_tot': self.pwnd_tot,
            'uptime': int(time.time() - self.start_time),
            'epoch': self.epoch,
            'policy': PERSONALITIES[self.personality]
        }
    
    def update_grid_data(self):
        """Update device data on opwngrid server by re-enrolling"""
        # opwngrid uses enrollment to update data, so just re-enroll
        return self.enroll()
    
    def _report_ap_batch(self, batch_id, start_idx, end_idx, total):
        """Report a batch of APs in a thread"""
        for i in range(start_idx, end_idx):
            if not self.token:  # Check if still enrolled
                break
            essid, bssid = self._generate_fake_ap()
            success = self.report_ap(essid, bssid)
            # Add small delay to avoid rate limiting
            time.sleep(0.05 if success else 0.5)
            
            # Progress update every 10 APs
            if (i - start_idx) > 0 and (i - start_idx) % 10 == 0:
                progress = ((i - start_idx + 1) / (end_idx - start_idx)) * 100
                print(f"[{self.name}] Thread {batch_id}: {progress:.0f}% ({i - start_idx + 1}/{end_idx - start_idx} APs)")
    
    def report_initial_aps(self):
        """Report initial access points to match the pwned count using multiple threads"""
        if self.pwnd_tot > 0 and self.token:
            # Calculate how many APs to actually report
            # For small counts, report all; for large counts, report a representative sample
            if self.pwnd_tot <= 100:
                actual_to_report = self.pwnd_tot
            elif self.pwnd_tot <= 1000:
                actual_to_report = min(self.pwnd_tot, 500)
            else:
                # For large counts (1K+), report proportionally more but cap at 5000
                actual_to_report = min(int(self.pwnd_tot * 0.01), 5000)  # 1% or 5000 max
            
            if actual_to_report > 0:
                threads_to_use = min(self.report_threads, actual_to_report)
                
                print(f"[{self.name}] Reporting {actual_to_report} APs (total pwned: {self.pwnd_tot}) using {threads_to_use} thread(s)...")
                
                if threads_to_use == 1:
                    # Single-threaded mode (original behavior)
                    for i in range(actual_to_report):
                        essid, bssid = self._generate_fake_ap()
                        self.report_ap(essid, bssid)
                        if i > 0 and i % 10 == 0:
                            time.sleep(1)
                        else:
                            time.sleep(0.1)
                else:
                    # Multi-threaded mode
                    batch_size = actual_to_report // threads_to_use
                    threads = []
                    
                    for t in range(threads_to_use):
                        start = t * batch_size
                        end = start + batch_size if t < threads_to_use - 1 else actual_to_report
                        
                        thread = threading.Thread(
                            target=self._report_ap_batch,
                            args=(t + 1, start, end, actual_to_report),
                            daemon=True
                        )
                        threads.append(thread)
                        thread.start()
                        time.sleep(0.1)  # Stagger thread starts
                    
                    # Wait for all threads to complete
                    for thread in threads:
                        thread.join()
                
                print(f"[{self.name}] ✓ Finished reporting APs")
    
    def run(self):
        """Main loop for the fake Pwnagotchi"""
        self.running = True
        print(f"[{self.name}] Starting...")
        
        # Enroll with opwngrid server
        if not self.enroll():
            print(f"[{self.name}] Failed to enroll, stopping")
            self.running = False
            return
        
        # Report initial access points if we have any
        if self.pwnd_tot > 0:
            self.report_initial_aps()
        
        while self.running:
            try:
                # Check if we've hit too many consecutive errors
                if self.consecutive_errors >= self.max_consecutive_errors:
                    if not self.paused:
                        self.paused = True
                        print(f"[{self.name}] ⏸️  Paused due to {self.consecutive_errors} consecutive errors")
                        
                        # Try rotating Tor circuit if enabled
                        if self.use_tor:
                            print(f"[{self.name}] 🔄 Attempting recovery with new Tor circuit...")
                            if self._rotate_tor_circuit():
                                # Try re-enrolling with new circuit
                                time.sleep(5)
                                if self.enroll():
                                    self.paused = False
                                    self.consecutive_errors = 0
                                    print(f"[{self.name}] ✓ Recovered successfully!")
                                else:
                                    print(f"[{self.name}] ⏸️  Still having issues, will retry in 60s")
                                    time.sleep(60)
                            else:
                                print(f"[{self.name}] ⏸️  Failed to rotate circuit, will retry in 60s")
                                time.sleep(60)
                        else:
                            print(f"[{self.name}] ⏸️  Too many errors without Tor, waiting 60s...")
                            time.sleep(60)
                            # Try again after waiting
                            if self.enroll():
                                self.paused = False
                                self.consecutive_errors = 0
                                print(f"[{self.name}] ✓ Recovered!")
                    else:
                        # Already paused, just wait
                        time.sleep(30)
                        continue
                
                # Normal operation if not paused
                if not self.paused:
                    # Update stats
                    self._update_stats()
                    
                    # Update grid data
                    if not self.update_grid_data():
                        # If update fails, increment will happen in enroll()
                        pass
                    
                    # Sleep
                    time.sleep(UPDATE_INTERVAL + random.randint(-5, 5))
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.consecutive_errors += 1
                print(f"[{self.name}] Error in main loop: {e}")
                time.sleep(UPDATE_INTERVAL)
        
        print(f"[{self.name}] Stopped")
    
    def stop(self):
        """Stop the fake Pwnagotchi"""
        self.running = False
        
        # Cleanup Tor process if running
        if self.tor_process:
            try:
                self.tor_process.terminate()
                self.tor_process.wait(timeout=5)
                print(f"[{self.name}] Tor stopped")
            except:
                self.tor_process.kill()


class GridTester:
    """Manages multiple fake Pwnagotchis"""
    
    def __init__(self, num_pwnies, opwngrid_url, use_tor=False, custom_pwned=None, custom_name=None, report_threads=1):
        self.num_pwnies = num_pwnies
        self.opwngrid_url = opwngrid_url
        self.use_tor = use_tor
        self.custom_pwned = custom_pwned
        self.custom_name = custom_name
        self.report_threads = report_threads
        self.pwnies = []
        self.threads = []
        
        # Create output directory
        os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    def create_pwnies(self):
        """Create fake Pwnagotchi instances"""
        print(f"\n=== Creating {self.num_pwnies} fake Pwnagotchis ===")
        if self.use_tor:
            print(f"    Using Tor for anonymity (SOCKS ports starting at {TOR_SOCKS_PORT_START})")
        print()
        
        for i in range(self.num_pwnies):
            tor_port = TOR_SOCKS_PORT_START + i if self.use_tor else None
            pwny = FakePwnagotchi(
                i, 
                self.opwngrid_url, 
                use_tor=self.use_tor, 
                tor_port=tor_port,
                custom_pwned=self.custom_pwned,
                custom_name=self.custom_name,
                report_threads=self.report_threads
            )
            self.pwnies.append(pwny)
            
            # Save keypair info
            self._save_pwny_info(pwny)
            
            time.sleep(0.5 if not self.use_tor else 1)  # Longer delay when using Tor
        
        print(f"\n=== Created {len(self.pwnies)} Pwnagotchis ===\n")
    
    def _save_pwny_info(self, pwny):
        """Save Pwnagotchi info to file"""
        info = {
            'id': pwny.pwny_id,
            'name': pwny.name,
            'fingerprint': pwny.fingerprint,
            'identity': pwny.identity,
            'public_key': pwny.keypair['public_b64'],
            'enrolled': hasattr(pwny, 'token') and pwny.token is not None,
            'token': getattr(pwny, 'token', ''),
            'pwnd_tot': pwny.pwnd_tot,
            'pwnd_run': pwny.pwnd_run,
            'epoch': pwny.epoch,
            'uptime': int(time.time() - pwny.start_time),
            'version': '1.5.5',
            'personality': pwny.personality,
            'use_tor': pwny.use_tor,
            'tor_port': pwny.tor_port,
            'session_data': pwny.session_data,
            'access_points': [],  # Don't save APs to keep file size small
            'created': datetime.now().isoformat(),
            'last_saved': datetime.now().isoformat()
        }
        
        filename = os.path.join(OUTPUT_DIR, f"{pwny.name}.json")
        with open(filename, 'w') as f:
            json.dump(info, f, indent=2)
        
        # Save private key to separate file
        key_filename = os.path.join(OUTPUT_DIR, f"{pwny.name}_private.pem")
        with open(key_filename, 'w') as f:
            f.write(pwny.keypair['private'])
    
    def start_all(self):
        """Start all fake Pwnagotchis in threads"""
        print("\n=== Starting all Pwnagotchis ===\n")
        
        for pwny in self.pwnies:
            thread = threading.Thread(target=pwny.run, daemon=True)
            thread.start()
            self.threads.append(thread)
            time.sleep(1)  # Stagger starts
        
        print(f"\n=== All {len(self.pwnies)} Pwnagotchis running ===")
        print(f"Press Ctrl+C to stop\n")
    
    def stop_all(self):
        """Stop all fake Pwnagotchis"""
        print("\n\n=== Stopping all Pwnagotchis ===\n")
        
        for pwny in self.pwnies:
            pwny.stop()
        
        # Wait for threads to finish
        for thread in self.threads:
            thread.join(timeout=5)
        
        # Save final state of all pwnies
        print("\n=== Saving pwnie states ===")
        for pwny in self.pwnies:
            self._save_pwny_info(pwny)
        
        print("\n=== All Pwnagotchis stopped ===")
    
    def print_summary(self):
        """Print summary statistics"""
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        
        total_handshakes = sum(p.pwnd_tot for p in self.pwnies)
        total_epochs = sum(p.epoch for p in self.pwnies)
        
        print(f"Total Pwnagotchis: {len(self.pwnies)}")
        print(f"Total Handshakes: {total_handshakes}")
        print(f"Total Epochs: {total_epochs}")
        print(f"Average Handshakes per Unit: {total_handshakes / len(self.pwnies):.1f}")
        
        print("\nTop 5 Performers:")
        sorted_pwnies = sorted(self.pwnies, key=lambda p: p.pwnd_tot, reverse=True)[:5]
        for i, pwny in enumerate(sorted_pwnies, 1):
            print(f"  {i}. {pwny.name}: {pwny.pwnd_tot} handshakes")
        
        print("="*60 + "\n")


def main():
    # Declare globals at the beginning
    global NUM_PWNIES, UPDATE_INTERVAL, OPWNGRID_API_URL, USE_TOR
    
    parser = argparse.ArgumentParser(
        description='Pwnagotchi Grid Test Generator - Create fake units on opwngrid.xyz',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate 10 units with random pwned counts
  python3 pwnagotchi-gen.py

  # Generate 25 units through Tor
  python3 pwnagotchi-gen.py --count 25 --tor

  # Generate 5 units with exactly 42 pwned networks each
  python3 pwnagotchi-gen.py --count 5 --pwned 42

  # Generate 15 units through Tor with random pwned counts (0-100)
  python3 pwnagotchi-gen.py --count 15 --tor --pwned random

Note: Using Tor requires 'tor' to be installed on your system.
      Each unit will use a separate Tor circuit for anonymity.
        """
    )
    
    parser.add_argument('-c', '--count', type=int, default=NUM_PWNIES,
                       help=f'Number of fake pwnagotchis to generate (default: {NUM_PWNIES})')
    parser.add_argument('-n', '--name', type=str, default=None,
                       help='Custom name for the pwnie (only works with --count 1)')
    parser.add_argument('-t', '--tor', action='store_true',
                       help='Route each unit through its own Tor circuit')
    parser.add_argument('--threads', type=int, default=1,
                       help='Number of parallel threads for AP reporting (default: 1, max: 50)')
    parser.add_argument('-p', '--pwned', type=str, default='random',
                       help='Number of pwned networks: a number (0-100), or "random" (default: random)')
    parser.add_argument('-i', '--interval', type=int, default=UPDATE_INTERVAL,
                       help=f'Update interval in seconds (default: {UPDATE_INTERVAL})')
    parser.add_argument('--api', type=str, default=OPWNGRID_API_URL,
                       help=f'opwngrid API URL (default: {OPWNGRID_API_URL})')
    parser.add_argument('-y', '--yes', '--no-confirm', action='store_true',
                       help='Skip confirmation prompt (for automation)')
    
    args = parser.parse_args()
    
    # Validate custom name
    if args.name and args.count != 1:
        print("Error: --name can only be used with --count 1")
        sys.exit(1)
    
    # Validate threads
    if args.threads < 1:
        print("Error: --threads must be at least 1")
        sys.exit(1)
    elif args.threads > 50:
        print("Error: --threads cannot exceed 50 (to avoid overwhelming the API)")
        sys.exit(1)
    
    # Parse pwned count
    custom_pwned = None
    if args.pwned.lower() != 'random':
        try:
            custom_pwned = int(args.pwned)
            if custom_pwned < 0 or custom_pwned > 1000000:
                print("Error: --pwned must be between 0 and 1000000, or 'random'")
                sys.exit(1)
        except ValueError:
            print("Error: --pwned must be a number or 'random'")
            sys.exit(1)
    
    # Update globals
    NUM_PWNIES = args.count
    UPDATE_INTERVAL = args.interval
    OPWNGRID_API_URL = args.api
    USE_TOR = args.tor
    
    print("""
    ╔═══════════════════════════════════════════════════════╗
    ║     Pwnagotchi Grid Test Generator                    ║
    ║     For Testing opwngrid.xyz with Fake Units          ║
    ╚═══════════════════════════════════════════════════════╝
    """)
    
    print(f"Configuration:")
    print(f"  opwngrid API URL: {OPWNGRID_API_URL}")
    print(f"  Number of Units: {NUM_PWNIES}")
    print(f"  Update Interval: {UPDATE_INTERVAL}s")
    print(f"  Output Directory: {OUTPUT_DIR}")
    print(f"  Using Tor: {'Yes' if USE_TOR else 'No'}")
    print(f"  Pwned Networks: {custom_pwned if custom_pwned is not None else 'Random (0-100)'}")
    if args.name:
        print(f"  Custom Name: {args.name}")
    if args.threads > 1:
        print(f"  Reporting Threads: {args.threads} (parallel AP reporting)")
    
    if USE_TOR:
        print(f"\n⚠️  Tor is enabled - make sure 'tor' is installed on your system!")
        print(f"  SOCKS ports will be: {TOR_SOCKS_PORT_START} - {TOR_SOCKS_PORT_START + NUM_PWNIES - 1}")
    
    # Skip confirmation if --yes flag is set
    if not args.yes:
        input("\nPress Enter to continue or Ctrl+C to abort...")
    else:
        print("\n🚀 Starting automatically (--yes flag set)...")
    
    # Create tester
    tester = GridTester(NUM_PWNIES, OPWNGRID_API_URL, use_tor=USE_TOR, custom_pwned=custom_pwned, custom_name=args.name, report_threads=args.threads)
    
    # Create fake pwnagotchis
    tester.create_pwnies()
    
    try:
        # Start all
        tester.start_all()
        
        # Keep running until interrupted
        while True:
            time.sleep(60)
            tester.print_summary()
            
    except KeyboardInterrupt:
        print("\n\nReceived interrupt signal...")
    finally:
        tester.stop_all()
        tester.print_summary()


if __name__ == "__main__":
    main()
    