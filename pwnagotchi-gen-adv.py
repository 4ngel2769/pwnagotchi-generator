#!/usr/bin/env python3
"""
Advanced Pwnagotchi Grid Testing Scenarios
Tests specific behaviors and edge cases
"""

import sys
import time
import random
import argparse
from datetime import datetime, timedelta

# Note: This module is a work in progress. For actual testing, use pwnagotchi-gen.py
# from pwny_grid_tester import FakePwnagotchi, GridTester

class TestScenarios:
    """Various test scenarios for grid behavior"""
    
    def __init__(self, grid_api_url, opwngrid_url):
        self.grid_api_url = grid_api_url
        self.opwngrid_url = opwngrid_url
    
    def test_peer_discovery(self, num_units=5, duration=300):
        """
        Test peer discovery mechanism
        Spawn units gradually and observe how they discover each other
        """
        print("\n=== TEST: Peer Discovery ===")
        print(f"Spawning {num_units} units over {duration} seconds")
        
        from pwny_grid_tester import FakePwnagotchi
        pwnies = []
        
        # Spawn units at intervals
        spawn_interval = duration / num_units
        
        for i in range(num_units):
            pwny = FakePwnagotchi(i, self.grid_api_url, self.opwngrid_url)
            pwnies.append(pwny)
            
            # Start in a thread
            import threading
            thread = threading.Thread(target=pwny.run, daemon=True)
            thread.start()
            
            print(f"Spawned {pwny.name} at {datetime.now().strftime('%H:%M:%S')}")
            
            if i < num_units - 1:
                time.sleep(spawn_interval)
        
        print(f"\nAll units spawned. Observing for 5 minutes...")
        time.sleep(300)
        
        # Stop all
        for pwny in pwnies:
            pwny.stop()
    
    def test_high_activity_unit(self, duration=600):
        """
        Test a single unit with extremely high activity
        Simulates a very successful hunting session
        """
        print("\n=== TEST: High Activity Unit ===")
        
        from pwny_grid_tester import FakePwnagotchi
        
        pwny = FakePwnagotchi(0, self.grid_api_url, self.opwngrid_url)
        
        # Override update method to generate lots of handshakes
        original_update = pwny._update_stats
        
        def aggressive_update():
            original_update()
            # Add 5-15 handshakes per update
            new_shakes = random.randint(5, 15)
            pwny.pwnd_run += new_shakes
            pwny.pwnd_tot += new_shakes
            pwny.session_data['handshakes'] = pwny.pwnd_run
            pwny.session_data['deauthed'] += random.randint(20, 50)
            pwny.session_data['associated'] += random.randint(10, 30)
        
        pwny._update_stats = aggressive_update
        
        print(f"Starting aggressive hunter: {pwny.name}")
        
        import threading
        thread = threading.Thread(target=pwny.run, daemon=True)
        thread.start()
        
        print(f"Running for {duration} seconds...")
        time.sleep(duration)
        
        pwny.stop()
        
        print(f"\nResults:")
        print(f"  Total Handshakes: {pwny.pwnd_tot}")
        print(f"  Total Epochs: {pwny.epoch}")
        print(f"  Deauths: {pwny.session_data['deauthed']}")
    
    def test_intermittent_units(self, num_units=10, on_duration=120, off_duration=60, cycles=5):
        """
        Test units that go online and offline
        Simulates real-world scenarios where devices aren't always on
        """
        print("\n=== TEST: Intermittent Connectivity ===")
        print(f"{num_units} units cycling {cycles} times")
        print(f"On: {on_duration}s, Off: {off_duration}s")
        
        from pwny_grid_tester import FakePwnagotchi
        import threading
        
        pwnies = []
        for i in range(num_units):
            pwny = FakePwnagotchi(i, self.grid_api_url, self.opwngrid_url)
            pwnies.append(pwny)
        
        for cycle in range(cycles):
            print(f"\n--- Cycle {cycle + 1}/{cycles} ---")
            
            # Start all units
            threads = []
            for pwny in pwnies:
                thread = threading.Thread(target=pwny.run, daemon=True)
                thread.start()
                threads.append(thread)
            
            print(f"Units ONLINE for {on_duration}s")
            time.sleep(on_duration)
            
            # Stop all units
            for pwny in pwnies:
                pwny.stop()
            
            print(f"Units OFFLINE for {off_duration}s")
            time.sleep(off_duration)
        
        print("\nTest complete")
    
    def test_location_clustering(self, num_clusters=3, units_per_cluster=5):
        """
        Test units in geographic clusters
        Simulates meetups or geographic distribution
        """
        print("\n=== TEST: Geographic Clustering ===")
        print(f"{num_clusters} clusters with {units_per_cluster} units each")
        
        from pwny_grid_tester import FakePwnagotchi
        import threading
        
        # Simulate clusters by using similar naming patterns
        cluster_names = ["NYC", "LAX", "CHI", "MIA", "SEA"][:num_clusters]
        
        all_pwnies = []
        
        for cluster_id, cluster_name in enumerate(cluster_names):
            print(f"\nCreating cluster: {cluster_name}")
            
            for i in range(units_per_cluster):
                pwny = FakePwnagotchi(
                    cluster_id * units_per_cluster + i,
                    self.grid_api_url,
                    self.opwngrid_url
                )
                # Override name to indicate cluster
                pwny.name = f"{cluster_name}_{pwny.name}"
                all_pwnies.append(pwny)
                
                thread = threading.Thread(target=pwny.run, daemon=True)
                thread.start()
                
                time.sleep(1)
        
        print(f"\nAll {len(all_pwnies)} units running")
        print("Press Ctrl+C to stop")
        
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            print("\nStopping all units...")
            for pwny in all_pwnies:
                pwny.stop()
    
    def test_rapid_spawn(self, num_units=50, spawn_rate=0.1):
        """
        Test rapid spawning of many units
        Tests grid's ability to handle sudden influx
        """
        print("\n=== TEST: Rapid Spawn ===")
        print(f"Spawning {num_units} units at {spawn_rate}s intervals")
        
        from pwny_grid_tester import FakePwnagotchi
        import threading
        
        pwnies = []
        threads = []
        
        start_time = time.time()
        
        for i in range(num_units):
            pwny = FakePwnagotchi(i, self.grid_api_url, self.opwngrid_url)
            pwnies.append(pwny)
            
            thread = threading.Thread(target=pwny.run, daemon=True)
            thread.start()
            threads.append(thread)
            
            if (i + 1) % 10 == 0:
                print(f"Spawned {i + 1}/{num_units} units...")
            
            time.sleep(spawn_rate)
        
        elapsed = time.time() - start_time
        print(f"\nAll {num_units} units spawned in {elapsed:.1f} seconds")
        print(f"Average spawn rate: {num_units/elapsed:.2f} units/second")
        
        print("\nLetting them run for 5 minutes...")
        time.sleep(300)
        
        print("\nStopping all units...")
        for pwny in pwnies:
            pwny.stop()
    
    def test_version_diversity(self, num_units=15):
        """
        Test different version numbers
        Ensures grid handles version diversity
        """
        print("\n=== TEST: Version Diversity ===")
        
        from pwny_grid_tester import FakePwnagotchi
        import threading
        
        versions = [
            "2.8.9", "2.8.8", "2.8.7", "2.8.6",
            "2.7.1", "2.6.5", "2.5.3"
        ]
        
        pwnies = []
        
        for i in range(num_units):
            pwny = FakePwnagotchi(i, self.grid_api_url, self.opwngrid_url)
            
            # Override version
            version = random.choice(versions)
            original_get_ad = pwny._get_advertisement_data
            
            def get_ad_with_version(v=version):
                data = original_get_ad()
                data['version'] = v
                return data
            
            pwny._get_advertisement_data = get_ad_with_version
            
            pwnies.append(pwny)
            
            thread = threading.Thread(target=pwny.run, daemon=True)
            thread.start()
            
            print(f"Spawned {pwny.name} with version {version}")
            time.sleep(1)
        
        print(f"\nRunning {num_units} units with mixed versions")
        print("Press Ctrl+C to stop")
        
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            print("\nStopping all units...")
            for pwny in pwnies:
                pwny.stop()


def main():
    parser = argparse.ArgumentParser(description="Advanced Grid Testing Scenarios")
    parser.add_argument("--api", default="http://opwnapi.yourdomain.tld:8666/api/v1",
                        help="Grid API URL")
    parser.add_argument("--opwngrid", default="http://opwnapi.yourdomain.tld/api/v1",
                        help="opwngrid API URL")
    
    subparsers = parser.add_subparsers(dest='scenario', help='Test scenario')
    
    # Peer discovery test
    peer = subparsers.add_parser('peer-discovery', help='Test peer discovery')
    peer.add_argument('--units', type=int, default=5, help='Number of units')
    peer.add_argument('--duration', type=int, default=300, help='Duration in seconds')
    
    # High activity test
    high = subparsers.add_parser('high-activity', help='Test high activity unit')
    high.add_argument('--duration', type=int, default=600, help='Duration in seconds')
    
    # Intermittent test
    inter = subparsers.add_parser('intermittent', help='Test intermittent connectivity')
    inter.add_argument('--units', type=int, default=10, help='Number of units')
    inter.add_argument('--on', type=int, default=120, help='Online duration')
    inter.add_argument('--off', type=int, default=60, help='Offline duration')
    inter.add_argument('--cycles', type=int, default=5, help='Number of cycles')
    
    # Clustering test
    cluster = subparsers.add_parser('clustering', help='Test geographic clustering')
    cluster.add_argument('--clusters', type=int, default=3, help='Number of clusters')
    cluster.add_argument('--per-cluster', type=int, default=5, help='Units per cluster')
    
    # Rapid spawn test
    rapid = subparsers.add_parser('rapid-spawn', help='Test rapid spawning')
    rapid.add_argument('--units', type=int, default=50, help='Number of units')
    rapid.add_argument('--rate', type=float, default=0.1, help='Spawn rate (seconds)')
    
    # Version diversity test
    version = subparsers.add_parser('version-diversity', help='Test version diversity')
    version.add_argument('--units', type=int, default=15, help='Number of units')
    
    args = parser.parse_args()
    
    if not args.scenario:
        parser.print_help()
        sys.exit(1)
    
    tester = TestScenarios(args.api, args.opwngrid)
    
    if args.scenario == 'peer-discovery':
        tester.test_peer_discovery(args.units, args.duration)
    elif args.scenario == 'high-activity':
        tester.test_high_activity_unit(args.duration)
    elif args.scenario == 'intermittent':
        tester.test_intermittent_units(args.units, args.on, args.off, args.cycles)
    elif args.scenario == 'clustering':
        tester.test_location_clustering(args.clusters, args.per_cluster)
    elif args.scenario == 'rapid-spawn':
        tester.test_rapid_spawn(args.units, args.rate)
    elif args.scenario == 'version-diversity':
        tester.test_version_diversity(args.units)


if __name__ == "__main__":
    main()
    