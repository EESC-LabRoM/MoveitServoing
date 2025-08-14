#!/usr/bin/env python3
"""
Simple Latency Analysis Script (No External Dependencies)

This script analyzes latency CSV files without requiring pandas, matplotlib, etc.
It provides basic statistics and insights using only Python standard library.
"""

import csv
import os
import glob
import statistics
import argparse
from collections import defaultdict
from datetime import datetime


class SimpleLatencyAnalyzer:
    """Simple latency analyzer using only standard library."""
    
    def __init__(self, csv_directory):
        self.csv_directory = csv_directory
        self.data = []
        
    def load_data(self):
        """Load latency data from CSV files."""
        latency_files = glob.glob(os.path.join(self.csv_directory, "*latencies*.csv"))
        
        if not latency_files:
            raise FileNotFoundError(f"No latency CSV files found in {self.csv_directory}")
            
        # Use the most recent file
        latest_file = max(latency_files, key=os.path.getctime)
        print(f"Loading data from: {latest_file}")
        
        with open(latest_file, 'r') as f:
            reader = csv.DictReader(f)
            self.data = [row for row in reader]
            
        print(f"Loaded {len(self.data)} cycles")
        
    def safe_float(self, value):
        """Safely convert value to float, return None if empty or invalid."""
        if not value or value == '':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
            
    def get_latency_stats(self, column_name):
        """Calculate statistics for a latency column."""
        values = []
        for row in self.data:
            val = self.safe_float(row.get(column_name, ''))
            if val is not None:
                values.append(val * 1000)  # Convert to ms
                
        if not values:
            return None
            
        return {
            'count': len(values),
            'mean': statistics.mean(values),
            'median': statistics.median(values),
            'stdev': statistics.stdev(values) if len(values) > 1 else 0,
            'min': min(values),
            'max': max(values)
        }
        
    def print_summary_statistics(self):
        """Print comprehensive summary statistics."""
        if not self.data:
            raise ValueError("No data loaded. Call load_data() first.")
            
        print("\n" + "="*70)
        print("SPOT TELEOPERATION LATENCY ANALYSIS (SIMPLE VERSION)")
        print("="*70)
        
        # Overall statistics
        print(f"\nTotal completed cycles: {len(self.data)}")
        
        # Mode breakdown
        mode_counts = defaultdict(int)
        for row in self.data:
            mode = row.get('mode', 'unknown')
            mode_counts[mode] += 1
            
        print(f"Mode breakdown:")
        for mode, count in mode_counts.items():
            print(f"  {mode}: {count} cycles")
            
        # Latency statistics
        latency_columns = [
            'total_latency', 'perception_latency', 'decision_latency', 
            'execution_latency', 'finger_count_latency', 'wrist_tf_latency', 
            'yolo_detection_latency'
        ]
        
        print(f"\n{'Latency Type':<25} {'Count':<7} {'Mean':<10} {'Median':<10} {'Std':<10} {'Min':<10} {'Max':<10}")
        print("-" * 87)
        
        for col in latency_columns:
            stats = self.get_latency_stats(col)
            if stats:
                name = col.replace('_', ' ').title()
                print(f"{name:<25} {stats['count']:<7} "
                      f"{stats['mean']:<10.1f} {stats['median']:<10.1f} "
                      f"{stats['stdev']:<10.1f} {stats['min']:<10.1f} {stats['max']:<10.1f}")
                      
        # Success rate
        success_count = 0
        total_success_rows = 0
        
        for row in self.data:
            success_val = row.get('success', '')
            if success_val != '':
                total_success_rows += 1
                if success_val.lower() in ['true', '1', 'yes']:
                    success_count += 1
                    
        if total_success_rows > 0:
            success_rate = (success_count / total_success_rows) * 100
            print(f"\nOverall success rate: {success_rate:.1f}% ({success_count}/{total_success_rows})")
            
        # Command type breakdown
        cmd_counts = defaultdict(int)
        for row in self.data:
            cmd = row.get('command_type', 'unknown')
            if cmd:
                cmd_counts[cmd] += 1
                
        if cmd_counts:
            print(f"\nCommand type distribution:")
            for cmd_type, count in cmd_counts.items():
                print(f"  {cmd_type}: {count} cycles")
                
        # Gesture breakdown
        gesture_counts = defaultdict(int)
        for row in self.data:
            gesture = row.get('gesture_value', '')
            if gesture != '':
                gesture_counts[f"gesture_{gesture}"] += 1
                
        if gesture_counts:
            print(f"\nGesture distribution:")
            for gesture, count in gesture_counts.items():
                print(f"  {gesture}: {count} cycles")
                
    def analyze_by_mode(self):
        """Analyze latencies by operation mode."""
        print(f"\n{'='*70}")
        print("LATENCY COMPARISON BY MODE")
        print("="*70)
        
        modes = set(row.get('mode', 'unknown') for row in self.data)
        
        for mode in sorted(modes):
            mode_data = [row for row in self.data if row.get('mode') == mode]
            if not mode_data:
                continue
                
            print(f"\n🔹 {mode.upper()} MODE ({len(mode_data)} cycles)")
            print("-" * 50)
            
            for col in ['total_latency', 'perception_latency', 'decision_latency', 'execution_latency']:
                stats = self.get_latency_stats_for_subset(mode_data, col)
                if stats:
                    name = col.replace('_', ' ').title()
                    print(f"  {name:<20}: {stats['mean']:.1f}ms ± {stats['stdev']:.1f}ms "
                          f"(range: {stats['min']:.1f}-{stats['max']:.1f}ms)")
                          
    def get_latency_stats_for_subset(self, subset_data, column_name):
        """Calculate statistics for a subset of data."""
        values = []
        for row in subset_data:
            val = self.safe_float(row.get(column_name, ''))
            if val is not None:
                values.append(val * 1000)  # Convert to ms
                
        if not values:
            return None
            
        return {
            'count': len(values),
            'mean': statistics.mean(values),
            'median': statistics.median(values),
            'stdev': statistics.stdev(values) if len(values) > 1 else 0,
            'min': min(values),
            'max': max(values)
        }
        
    def find_outliers(self):
        """Find cycles with unusually high latencies."""
        print(f"\n{'='*70}")
        print("OUTLIER ANALYSIS")
        print("="*70)
        
        # Find cycles with total latency > 1 second
        high_latency_cycles = []
        for row in self.data:
            total_lat = self.safe_float(row.get('total_latency', ''))
            if total_lat and total_lat > 1.0:  # > 1 second
                high_latency_cycles.append((row['cycle_id'], total_lat * 1000))
                
        if high_latency_cycles:
            print(f"\n🚨 High latency cycles (>1000ms):")
            for cycle_id, latency in sorted(high_latency_cycles, key=lambda x: x[1], reverse=True):
                print(f"  {cycle_id}: {latency:.1f}ms")
        else:
            print(f"\n✅ No high latency cycles found (all <1000ms)")
            
        # Find failed commands
        failed_cycles = []
        for row in self.data:
            success = row.get('success', '').lower()
            if success in ['false', '0', 'no']:
                cycle_id = row.get('cycle_id', 'unknown')
                cmd_type = row.get('command_type', 'unknown')
                failed_cycles.append((cycle_id, cmd_type))
                
        if failed_cycles:
            print(f"\n❌ Failed command cycles:")
            for cycle_id, cmd_type in failed_cycles:
                print(f"  {cycle_id}: {cmd_type}")
        else:
            print(f"\n✅ All commands succeeded")
            
    def generate_simple_report(self):
        """Generate a simple text report."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(self.csv_directory, f"simple_latency_report_{timestamp}.txt")
        
        with open(report_path, 'w') as f:
            # Redirect print output to file
            import sys
            original_stdout = sys.stdout
            sys.stdout = f
            
            self.print_summary_statistics()
            self.analyze_by_mode()
            self.find_outliers()
            
            # Restore stdout
            sys.stdout = original_stdout
            
        print(f"\n📄 Simple analysis report saved to: {report_path}")
        return report_path


def main():
    """Main entry point."""
    # Default directory - logs folder in the package
    script_dir = os.path.dirname(os.path.abspath(__file__))
    package_dir = os.path.dirname(script_dir)
    default_csv_dir = os.path.join(package_dir, "logs")
    
    parser = argparse.ArgumentParser(description="Simple Spot latency data analysis")
    parser.add_argument("csv_directory", nargs='?', default=default_csv_dir,
                       help=f"Directory containing latency CSV files (default: {default_csv_dir})")
    parser.add_argument("--summary-only", action="store_true", 
                       help="Only print summary statistics")
    parser.add_argument("--generate-report", action="store_true",
                       help="Generate a text report file")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.csv_directory):
        print(f"Error: Directory {args.csv_directory} does not exist")
        return 1
        
    try:
        analyzer = SimpleLatencyAnalyzer(args.csv_directory)
        analyzer.load_data()
        
        if args.summary_only:
            analyzer.print_summary_statistics()
        elif args.generate_report:
            analyzer.generate_simple_report()
        else:
            analyzer.print_summary_statistics()
            analyzer.analyze_by_mode()
            analyzer.find_outliers()
            
    except Exception as e:
        print(f"Error during analysis: {e}")
        return 1
        
    return 0


if __name__ == "__main__":
    exit(main())
