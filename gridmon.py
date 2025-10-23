#!/usr/bin/env python3
"""
Grid Monitoring and Analysis Tool
Monitor and analyze the behavior of your test opwngrid instance
"""

import requests
import json
import time
import argparse
from datetime import datetime
from collections import defaultdict
import statistics

class GridMonitor:
    """Monitor and analyze grid behavior"""
    
    def __init__(self, grid_api_url, opwngrid_url):
        self.grid_api_url = grid_api_url
        self.opwngrid_url = opwngrid_url
        self.history = []
        self.peer_history = defaultdict(list)
    
    def check_grid_health(self):
        """Check if grid is responding"""
        try:
            response = requests.get(f"{self.opwngrid_url}/uptime", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return True, data
            return False, None
        except Exception as e:
            return False, str(e)
    
    def get_peers(self):
        """Get all peers from the grid"""
        try:
            url = f"{self.grid_api_url}/mesh/peers"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            print(f"Error getting peers: {e}")
            return []
    
    def get_memory(self):
        """Get grid memory/state"""
        try:
            url = f"{self.grid_api_url}/mesh/memory"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error getting memory: {e}")
            return None
    
    def analyze_peers(self, peers):
        """Analyze peer data"""
        if not peers:
            return None
        
        analysis = {
            'total_peers': len(peers),
            'total_handshakes': 0,
            'avg_uptime': 0,
            'versions': defaultdict(int),
            'personalities': defaultdict(int),
            'most_active': None,
            'newest': None,
            'oldest_uptime': 0,
        }
        
        uptimes = []
        handshakes = []
        
        for peer in peers:
            # Extract data safely
            adv = peer.get('advertisement', {})
            
            # Count handshakes
            pwnd = adv.get('pwnd_tot', 0)
            analysis['total_handshakes'] += pwnd
            handshakes.append((peer.get('identity', 'unknown')[:8], pwnd))
            
            # Track uptime
            uptime = adv.get('uptime', 0)
            uptimes.append(uptime)
            
            # Track versions
            version = adv.get('version', 'unknown')
            analysis['versions'][version] += 1
            
            # Track personalities
            policy = adv.get('policy', {})
            if policy.get('deauth') and policy.get('associate'):
                personality = 'aggressive'
            elif not policy.get('deauth') and policy.get('associate'):
                personality = 'passive'
            else:
                personality = 'balanced'
            analysis['personalities'][personality] += 1
        
        # Calculate averages
        if uptimes:
            analysis['avg_uptime'] = statistics.mean(uptimes)
            analysis['oldest_uptime'] = max(uptimes)
        
        # Find most active
        if handshakes:
            handshakes.sort(key=lambda x: x[1], reverse=True)
            analysis['most_active'] = handshakes[:5]
        
        return analysis
    
    def print_snapshot(self, peers, analysis):
        """Print a snapshot of current grid state"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        print("\n" + "="*70)
        print(f"GRID SNAPSHOT - {timestamp}")
        print("="*70)
        
        # Health check
        healthy, health_data = self.check_grid_health()
        if healthy:
            print(f"✓ Grid Status: HEALTHY")
            if health_data and 'isUp' in health_data:
                print(f"  API responding: {health_data.get('isUp', False)}")
        else:
            print(f"✗ Grid Status: UNHEALTHY - {health_data}")
        
        print()
        
        if not peers:
            print("No peers detected")
            return
        
        # Basic stats
        print(f"Total Peers: {analysis['total_peers']}")
        print(f"Total Handshakes: {analysis['total_handshakes']}")
        print(f"Average Uptime: {self._format_uptime(analysis['avg_uptime'])}")
        print(f"Longest Running: {self._format_uptime(analysis['oldest_uptime'])}")
        
        print()
        
        # Version distribution
        print("Version Distribution:")
        for version, count in sorted(analysis['versions'].items(), key=lambda x: x[1], reverse=True):
            percentage = (count / analysis['total_peers']) * 100
            print(f"  {version}: {count} ({percentage:.1f}%)")
        
        print()
        
        # Personality distribution
        print("Personality Distribution:")
        for personality, count in sorted(analysis['personalities'].items(), key=lambda x: x[1], reverse=True):
            percentage = (count / analysis['total_peers']) * 100
            print(f"  {personality}: {count} ({percentage:.1f}%)")
        
        print()
        
        # Most active peers
        if analysis['most_active']:
            print("Most Active Peers (by handshakes):")
            for i, (peer_id, handshakes) in enumerate(analysis['most_active'], 1):
                print(f"  {i}. {peer_id}...: {handshakes} handshakes")
        
        print("="*70)
    
    def _format_uptime(self, seconds):
        """Format uptime in human-readable format"""
        hours, remainder = divmod(int(seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    def monitor_continuous(self, interval=30, duration=None):
        """Continuously monitor the grid"""
        print(f"\nStarting continuous monitoring (interval: {interval}s)")
        if duration:
            print(f"Will run for {duration} seconds")
        print("Press Ctrl+C to stop\n")
        
        start_time = time.time()
        snapshot_count = 0
        
        try:
            while True:
                # Check if duration exceeded
                if duration and (time.time() - start_time) >= duration:
                    print("\nDuration reached, stopping...")
                    break
                
                # Get current state
                peers = self.get_peers()
                analysis = self.analyze_peers(peers)
                
                # Store in history
                self.history.append({
                    'timestamp': datetime.now(),
                    'peers': len(peers),
                    'handshakes': analysis['total_handshakes'] if analysis else 0
                })
                
                # Print snapshot
                self.print_snapshot(peers, analysis)
                
                snapshot_count += 1
                
                # Wait for next interval
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped by user")
        
        # Print summary
        self.print_monitoring_summary(snapshot_count)
    
    def print_monitoring_summary(self, snapshot_count):
        """Print summary of monitoring session"""
        if not self.history:
            return
        
        print("\n" + "="*70)
        print("MONITORING SESSION SUMMARY")
        print("="*70)
        
        print(f"Snapshots taken: {snapshot_count}")
        print(f"Duration: {self._format_uptime((self.history[-1]['timestamp'] - self.history[0]['timestamp']).total_seconds())}")
        
        # Peer count over time
        peer_counts = [h['peers'] for h in self.history]
        print(f"\nPeer Count:")
        print(f"  Min: {min(peer_counts)}")
        print(f"  Max: {max(peer_counts)}")
        print(f"  Avg: {statistics.mean(peer_counts):.1f}")
        
        # Handshake growth
        handshake_counts = [h['handshakes'] for h in self.history]
        if len(handshake_counts) > 1:
            growth = handshake_counts[-1] - handshake_counts[0]
            print(f"\nHandshake Growth:")
            print(f"  Start: {handshake_counts[0]}")
            print(f"  End: {handshake_counts[-1]}")
            print(f"  Growth: +{growth}")
            
            if growth > 0:
                duration = (self.history[-1]['timestamp'] - self.history[0]['timestamp']).total_seconds()
                rate = growth / (duration / 3600)  # per hour
                print(f"  Rate: {rate:.1f} handshakes/hour")
        
        print("="*70 + "\n")
    
    def export_data(self, filename="grid_analysis.json"):
        """Export collected data to JSON"""
        export_data = {
            'monitoring_started': self.history[0]['timestamp'].isoformat() if self.history else None,
            'monitoring_ended': self.history[-1]['timestamp'].isoformat() if self.history else None,
            'snapshots': len(self.history),
            'history': [
                {
                    'timestamp': h['timestamp'].isoformat(),
                    'peers': h['peers'],
                    'handshakes': h['handshakes']
                }
                for h in self.history
            ]
        }
        
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"Data exported to {filename}")
    
    def stress_test_analysis(self, max_peers_expected):
        """Analyze grid behavior under stress"""
        print("\n=== STRESS TEST ANALYSIS ===\n")
        
        peers = self.get_peers()
        analysis = self.analyze_peers(peers)
        
        if not analysis:
            print("No peers detected - grid may be down")
            return
        
        # Check peer capacity
        peer_capacity = (analysis['total_peers'] / max_peers_expected) * 100
        print(f"Peer Capacity: {analysis['total_peers']}/{max_peers_expected} ({peer_capacity:.1f}%)")
        
        if peer_capacity >= 90:
            print("⚠ WARNING: Near capacity!")
        elif peer_capacity >= 100:
            print("✗ CRITICAL: Over capacity!")
        else:
            print("✓ Capacity OK")
        
        # Check response time
        start = time.time()
        self.get_peers()
        response_time = time.time() - start
        
        print(f"\nAPI Response Time: {response_time:.3f}s")
        if response_time > 5:
            print("⚠ WARNING: Slow response")
        elif response_time > 10:
            print("✗ CRITICAL: Very slow response")
        else:
            print("✓ Response time OK")
        
        # Memory usage
        memory = self.get_memory()
        if memory:
            print(f"\nGrid Memory State:")
            print(json.dumps(memory, indent=2))
        
        print("\n" + "="*70)


def main():
    parser = argparse.ArgumentParser(description="Grid Monitoring and Analysis")
    parser.add_argument("--api", default="http://127.0.0.1:8666/api/v1",
                        help="Grid API URL")
    parser.add_argument("--opwngrid", default="http://opwnapi.yourdomain.tld/api/v1",
                        help="opwngrid API URL")
    
    subparsers = parser.add_subparsers(dest='command', help='Command')
    
    # Snapshot command
    snapshot = subparsers.add_parser('snapshot', help='Take a single snapshot')
    
    # Monitor command
    monitor = subparsers.add_parser('monitor', help='Continuous monitoring')
    monitor.add_argument('--interval', type=int, default=30, help='Interval in seconds')
    monitor.add_argument('--duration', type=int, default=None, help='Duration in seconds')
    monitor.add_argument('--export', type=str, default=None, help='Export data to file')
    
    # Stress test command
    stress = subparsers.add_parser('stress', help='Stress test analysis')
    stress.add_argument('--max-peers', type=int, default=100, help='Expected max peers')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    monitor = GridMonitor(args.api, args.opwngrid)
    
    if args.command == 'snapshot':
        peers = monitor.get_peers()
        analysis = monitor.analyze_peers(peers)
        monitor.print_snapshot(peers, analysis)
    
    elif args.command == 'monitor':
        monitor.monitor_continuous(args.interval, args.duration)
        if args.export:
            monitor.export_data(args.export)
    
    elif args.command == 'stress':
        monitor.stress_test_analysis(args.max_peers)


if __name__ == "__main__":
    main()
    