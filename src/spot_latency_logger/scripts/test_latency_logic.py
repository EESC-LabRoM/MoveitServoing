#!/usr/bin/env python3
"""
Test script to verify latency logger logic without ROS dependencies.
This simulates the latency measurement system to ensure the logic is correct.
"""

import time
import csv
import os
from collections import deque, defaultdict
from datetime import datetime
import random


class MockLatencyMeasurement:
    """Mock version of LatencyMeasurement for testing."""
    
    def __init__(self, cycle_id):
        self.cycle_id = cycle_id
        self.timestamps = {}
        self.metadata = {}
        self.completed = False
        
    def add_timestamp(self, event, timestamp, metadata=None):
        self.timestamps[event] = timestamp
        if metadata:
            self.metadata[event] = metadata
            
    def is_complete(self):
        required_events = ['T1_image', 'T2_gesture', 'T5_command', 'T6_feedback']
        return all(event in self.timestamps for event in required_events)
        
    def get_latencies(self):
        if not self.is_complete():
            return None
            
        latencies = {}
        timestamps = self.timestamps
        
        # Basic pipeline latencies
        latencies['perception_latency'] = timestamps['T2_gesture'] - timestamps['T1_image']
        latencies['decision_latency'] = timestamps['T5_command'] - timestamps['T2_gesture']
        latencies['execution_latency'] = timestamps['T6_feedback'] - timestamps['T5_command']
        latencies['total_latency'] = timestamps['T6_feedback'] - timestamps['T1_image']
        
        # Optional latencies if data is available
        if 'T3_finger_count' in timestamps:
            latencies['finger_count_latency'] = timestamps['T3_finger_count'] - timestamps['T2_gesture']
            
        if 'T4a_wrist_tf' in timestamps:
            latencies['wrist_tf_latency'] = timestamps['T4a_wrist_tf'] - timestamps['T1_image']
            
        if 'T4b_yolo' in timestamps:
            latencies['yolo_detection_latency'] = timestamps['T4b_yolo'] - timestamps['T1_image']
            
        return latencies


class MockLatencyLogger:
    """Mock version of LatencyLogger for testing."""
    
    def __init__(self, output_dir="/tmp/mock_latency_test"):
        self.csv_output_dir = output_dir
        os.makedirs(self.csv_output_dir, exist_ok=True)
        
        self.active_cycles = {}
        self.completed_cycles = deque(maxlen=100)
        self.cycle_counter = 0
        
        # Setup CSV files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        latency_file = os.path.join(self.csv_output_dir, f'mock_latencies_{timestamp}.csv')
        self.csv_file = open(latency_file, 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        
        # Write header
        header = [
            'cycle_id', 'timestamp', 'mode',
            'T1_image', 'T2_gesture', 'T3_finger_count', 'T4a_wrist_tf', 'T4b_yolo', 'T5_command', 'T6_feedback',
            'perception_latency', 'decision_latency', 'execution_latency', 'total_latency',
            'finger_count_latency', 'wrist_tf_latency', 'yolo_detection_latency',
            'gesture_value', 'finger_count', 'command_type', 'success'
        ]
        self.csv_writer.writerow(header)
        
    def generate_cycle_id(self):
        self.cycle_counter += 1
        return f"mock_cycle_{self.cycle_counter}_{int(time.time() * 1000)}"
        
    def simulate_pipeline_cycle(self, mode="manual"):
        """Simulate a complete pipeline cycle with realistic timing."""
        cycle_id = self.generate_cycle_id()
        measurement = MockLatencyMeasurement(cycle_id)
        
        # Simulate realistic timing (in seconds)
        base_time = time.time()
        
        # T1: Image capture (base)
        t1 = base_time
        measurement.add_timestamp('T1_image', t1, {'width': 640, 'height': 480})
        
        # T2: Gesture detection (50-200ms after image)
        t2 = t1 + random.uniform(0.05, 0.2)
        gesture_value = random.choice([0, 1])
        measurement.add_timestamp('T2_gesture', t2, {'gesture_value': gesture_value})
        
        # T3: Finger count (optional, if gesture == 1)
        if gesture_value == 1:
            t3 = t2 + random.uniform(0.1, 0.5)  # Service call latency
            finger_count = random.choice(['1', '2'])
            measurement.add_timestamp('T3_finger_count', t3, {
                'success': True, 'finger_count': finger_count
            })
        
        # T4a: Wrist TF (20-100ms after image)
        t4a = t1 + random.uniform(0.02, 0.1)
        measurement.add_timestamp('T4a_wrist_tf', t4a, {'frame': 'wrist'})
        
        # T4b: YOLO detection (100-500ms after image)
        t4b = t1 + random.uniform(0.1, 0.5)
        object_class = random.choice(['bottle', 'cup', 'phone', 'book'])
        confidence = random.uniform(0.6, 0.95)
        measurement.add_timestamp('T4b_yolo', t4b, {
            'object_class': object_class, 'confidence': confidence
        })
        
        # T5: Command sent (10-100ms after gesture)
        t5 = t2 + random.uniform(0.01, 0.1)
        command_type = random.choice(['arm_pose', 'gripper_open', 'gripper_close'])
        measurement.add_timestamp('T5_command', t5, {'command_type': command_type})
        
        # T6: Execution feedback (100-500ms after command)
        t6 = t5 + random.uniform(0.1, 0.5)
        success = random.choice([True, True, True, False])  # 75% success rate
        measurement.add_timestamp('T6_feedback', t6, {
            'success': success, 'message': 'Command executed' if success else 'Failed'
        })
        
        # Add to completed cycles
        if measurement.is_complete():
            measurement.completed = True
            self.completed_cycles.append(measurement)
            self.write_measurement_to_csv(measurement)
            
        return measurement
        
    def write_measurement_to_csv(self, measurement):
        """Write a measurement to the CSV file."""
        latencies = measurement.get_latencies()
        if not latencies:
            return
            
        timestamps = measurement.timestamps
        metadata = measurement.metadata
        
        # Extract metadata
        gesture_value = metadata.get('T2_gesture', {}).get('gesture_value', '')
        finger_count = metadata.get('T3_finger_count', {}).get('finger_count', '')
        command_type = metadata.get('T5_command', {}).get('command_type', '')
        success = metadata.get('T6_feedback', {}).get('success', '')
        
        # Determine mode
        mode = 'manual' if finger_count in ['1', '2'] else 'unknown'
        
        row = [
            measurement.cycle_id,
            timestamps.get('T1_image', 0),
            mode,
            timestamps.get('T1_image', 0),
            timestamps.get('T2_gesture', 0),
            timestamps.get('T3_finger_count', 0),
            timestamps.get('T4a_wrist_tf', 0),
            timestamps.get('T4b_yolo', 0),
            timestamps.get('T5_command', 0),
            timestamps.get('T6_feedback', 0),
            latencies.get('perception_latency', ''),
            latencies.get('decision_latency', ''),
            latencies.get('execution_latency', ''),
            latencies.get('total_latency', ''),
            latencies.get('finger_count_latency', ''),
            latencies.get('wrist_tf_latency', ''),
            latencies.get('yolo_detection_latency', ''),
            gesture_value,
            finger_count,
            command_type,
            success
        ]
        
        self.csv_writer.writerow(row)
        print(f"✓ Logged cycle {measurement.cycle_id}: "
              f"total_latency={latencies['total_latency']:.3f}s")
              
    def close(self):
        """Close CSV file."""
        self.csv_file.close()


def test_latency_measurement_system():
    """Test the latency measurement system with simulated data."""
    print("🧪 Testing Spot Teleoperation Latency Measurement System")
    print("=" * 60)
    
    # Create mock logger
    logger = MockLatencyLogger()
    
    # Simulate multiple pipeline cycles
    print("\n📊 Simulating pipeline cycles...")
    num_cycles = 20
    
    for i in range(num_cycles):
        mode = random.choice(['manual', 'semi_auto'])
        measurement = logger.simulate_pipeline_cycle(mode)
        
        # Small delay between cycles
        time.sleep(0.1)
        
    # Close logger
    logger.close()
    
    # Print summary
    print(f"\n✅ Successfully simulated {num_cycles} pipeline cycles")
    print(f"📁 Output directory: {logger.csv_output_dir}")
    
    # Show file contents
    csv_files = [f for f in os.listdir(logger.csv_output_dir) if f.endswith('.csv')]
    if csv_files:
        csv_path = os.path.join(logger.csv_output_dir, csv_files[0])
        print(f"📄 Generated CSV: {csv_path}")
        
        # Show first few lines
        with open(csv_path, 'r') as f:
            lines = f.readlines()
            print(f"\n📋 Sample data (first 3 rows):")
            for i, line in enumerate(lines[:3]):
                print(f"  {i}: {line.strip()}")
                
        print(f"\n📈 Total data rows: {len(lines) - 1}")  # Exclude header


if __name__ == "__main__":
    test_latency_measurement_system()
