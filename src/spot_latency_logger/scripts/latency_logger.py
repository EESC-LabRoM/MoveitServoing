#!/usr/bin/env python3
"""
Latency Logger Node for Spot Teleoperation Pipeline

This node measures end-to-end latency across the perception-decision-action pipeline:
T1: Camera image capture
T2: Hand gesture detection
T3: Finger count service response
T4a: Wrist TF broadcast
T4b: YOLO object detection
T5: Spot command sent
T6: Spot execution feedback

Saves latency measurements to CSV files for analysis.
"""

import rospy
import csv
import os
import time
from datetime import datetime
from collections import defaultdict, deque
from threading import Lock

# ROS message imports
from sensor_msgs.msg import Image
from std_msgs.msg import Int32
from geometry_msgs.msg import TransformStamped
from tf2_msgs.msg import TFMessage
from std_srvs.srv import Trigger

# Custom message imports (will be generated after catkin build)
try:
    from spot_latency_logger.msg import SpotCommand, SpotFeedback, YoloDetection
except ImportError:
    rospy.logwarn("Custom messages not found. Please run catkin build first.")
    # Define dummy classes for development
    class SpotCommand:
        def __init__(self):
            self.header = None
            self.command_type = ""
            
    class SpotFeedback:
        def __init__(self):
            self.header = None
            self.command_type = ""
            self.success = False
            
    class YoloDetection:
        def __init__(self):
            self.header = None
            self.object_class = ""


class LatencyMeasurement:
    """Stores timing data for a complete pipeline cycle."""
    
    def __init__(self, cycle_id):
        self.cycle_id = cycle_id
        self.timestamps = {}
        self.metadata = {}
        self.completed = False
        
    def add_timestamp(self, event, timestamp, metadata=None):
        """Add a timestamp for a specific event."""
        self.timestamps[event] = timestamp
        if metadata:
            self.metadata[event] = metadata
            
    def is_complete(self):
        """Check if all required timestamps are available."""
        required_events = ['T1_image', 'T2_gesture_recv', 'T5_command_recv', 'T6_feedback_recv']
        return all(event in self.timestamps for event in required_events)
        
    def get_latencies(self):
        """Calculate latencies between different stages."""
        if not self.is_complete():
            return None
            
        latencies = {}
        timestamps = self.timestamps
        
        # Perception: sensor→reconhecimento (mesmo frame timestamp)
        if 'T1_image' in timestamps and 'T2_gesture' in timestamps:
            latencies['perception_latency'] = (timestamps['T2_gesture'] - timestamps['T1_image']).to_sec()
        
        # Decision: do callback do gesto até o callback do comando (recv_ts)
        if 'T2_gesture_recv' in timestamps and 'T5_command_recv' in timestamps:
            latencies['decision_latency'] = (timestamps['T5_command_recv'] - timestamps['T2_gesture_recv']).to_sec()
        
        # Execution: do callback do comando até o callback do feedback (recv_ts)
        if 'T5_command_recv' in timestamps and 'T6_feedback_recv' in timestamps:
            latencies['execution_latency'] = (timestamps['T6_feedback_recv'] - timestamps['T5_command_recv']).to_sec()
        
        # Total E2E: captura do frame até receber feedback
        if 'T1_image' in timestamps and 'T6_feedback_recv' in timestamps:
            latencies['total_latency'] = (timestamps['T6_feedback_recv'] - timestamps['T1_image']).to_sec()
        
        # Optional latencies if data is available
        if 'T3_finger_count_recv' in timestamps and 'T2_gesture_recv' in timestamps:
            latencies['finger_count_latency'] = (timestamps['T3_finger_count_recv'] - timestamps['T2_gesture_recv']).to_sec()
            
        if 'T4a_wrist_tf' in timestamps:
            latencies['wrist_tf_latency'] = (timestamps['T4a_wrist_tf'] - timestamps['T1_image']).to_sec()
            
        if 'T4b_yolo' in timestamps:
            latencies['yolo_detection_latency'] = (timestamps['T4b_yolo'] - timestamps['T1_image']).to_sec()
            
        return latencies


class LatencyLogger:
    """Main latency logging node."""
    
    def __init__(self):
        rospy.init_node('latency_logger', anonymous=False)
        
        # Configuration
        # Get the package directory and create logs folder inside it
        import rospkg
        rospack = rospkg.RosPack()
        package_path = rospack.get_path('spot_latency_logger')
        default_log_dir = os.path.join(package_path, 'logs')
        
        self.csv_output_dir = rospy.get_param('~output_dir', default_log_dir)
        self.max_cycle_age = rospy.get_param('~max_cycle_age_sec', 10.0)  # Seconds
        self.buffer_size = rospy.get_param('~buffer_size', 100)
        
        # Create output directory
        os.makedirs(self.csv_output_dir, exist_ok=True)
        
        # Thread safety
        self.lock = Lock()
        
        # Data storage
        self.active_cycles = {}  # cycle_id -> LatencyMeasurement
        self.completed_cycles = deque(maxlen=self.buffer_size)
        self.cycle_counter = 0
        
        # Latest data for association
        self.latest_image_timestamp = None
        self.latest_gesture_value = None
        self.latest_finger_count_response_time = None
        
        # CSV writers
        self.csv_files = {}
        self.csv_writers = {}
        self._setup_csv_files()
        
        # Subscribers
        self._setup_subscribers()
        
        # Service clients
        self.finger_count_client = None
        self._setup_service_clients()
        
        # Cleanup timer
        rospy.Timer(rospy.Duration(1.0), self._cleanup_old_cycles)
        
        # Periodic save timer
        rospy.Timer(rospy.Duration(5.0), self._save_completed_cycles)
        
        rospy.loginfo("Latency Logger initialized. Output directory: %s", self.csv_output_dir)
        
    def _setup_csv_files(self):
        """Setup CSV files for logging."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Main latency file
        latency_file = os.path.join(self.csv_output_dir, f'spot_latencies_{timestamp}.csv')
        self.csv_files['latencies'] = open(latency_file, 'w', newline='')
        self.csv_writers['latencies'] = csv.writer(self.csv_files['latencies'])
        
        # Write header
        header = [
            'cycle_id', 'timestamp', 'mode',
            'T1_image', 'T2_gesture', 'T4a_wrist_tf', 'T4b_yolo', 'T5_command', 'T6_feedback',
            'T1_image_recv', 'T2_gesture_recv', 'T3_finger_count_recv', 'T5_command_recv', 'T6_feedback_recv',
            'perception_latency', 'decision_latency', 'execution_latency', 'total_latency',
            'finger_count_latency', 'wrist_tf_latency', 'yolo_detection_latency',
            'gesture_value', 'finger_count', 'command_type', 'success'
        ]
        self.csv_writers['latencies'].writerow(header)
        
        # Events log for debugging
        events_file = os.path.join(self.csv_output_dir, f'spot_events_{timestamp}.csv')
        self.csv_files['events'] = open(events_file, 'w', newline='')
        self.csv_writers['events'] = csv.writer(self.csv_files['events'])
        
        events_header = ['timestamp', 'event_type', 'cycle_id', 'data', 'metadata']
        self.csv_writers['events'].writerow(events_header)
        
    def _setup_subscribers(self):
        """Setup ROS subscribers."""
        # T1: Image capture
        rospy.Subscriber('/camera/color/image_raw', Image, self._on_image, queue_size=1)
        
        # T2: Hand gesture
        rospy.Subscriber('/hand_gesture', Int32, self._on_gesture, queue_size=1)
        
        # T3: Finger count result (from continuous_direct_grasp.py)
        from std_msgs.msg import Header
        rospy.Subscriber('/finger_count_result', Header, self._on_finger_count_result, queue_size=1)
        
        # T4a: TF broadcasts (wrist frame)
        rospy.Subscriber('/tf', TFMessage, self._on_tf, queue_size=10)
        
        # T4b: YOLO detections
        rospy.Subscriber('/yolo/detection', YoloDetection, self._on_yolo_detection, queue_size=1)
        
        # T5: Spot commands
        rospy.Subscriber('/spot/cmd_sent', SpotCommand, self._on_spot_command, queue_size=1)
        
        # T6: Spot feedback
        rospy.Subscriber('/spot/exec_done', SpotFeedback, self._on_spot_feedback, queue_size=1)
        
    def _setup_service_clients(self):
        """Setup service clients."""
        try:
            rospy.wait_for_service('/finger_count_node/get_finger_count', timeout=5.0)
            self.finger_count_client = rospy.ServiceProxy('/finger_count_node/get_finger_count', Trigger)
            rospy.loginfo("Finger count service client ready")
        except rospy.ROSException:
            rospy.logwarn("Finger count service not available")
            
    def _generate_cycle_id(self):
        """Generate a new cycle ID."""
        self.cycle_counter += 1
        return f"cycle_{self.cycle_counter}_{int(time.time() * 1000)}"
        
    def _log_event(self, event_type, cycle_id=None, data=None, metadata=None):
        """Log an event to the events CSV."""
        with self.lock:
            timestamp = rospy.Time.now().to_sec()
            self.csv_writers['events'].writerow([
                timestamp, event_type, cycle_id or 'N/A', 
                str(data) if data else '', str(metadata) if metadata else ''
            ])
            self.csv_files['events'].flush()
            
    def _on_image(self, msg):
        """T1: Handle camera image callback."""
        self.latest_image_timestamp = msg.header.stamp
        cycle_id = self._generate_cycle_id()
        
        with self.lock:
            measurement = LatencyMeasurement(cycle_id)
            measurement.add_timestamp('T1_image', msg.header.stamp, {
                'width': msg.width,
                'height': msg.height,
                'encoding': msg.encoding
            })
            measurement.add_timestamp('T1_image_recv', rospy.Time.now(), {
                'recv_context': 'callback_entry'
            })
            self.active_cycles[cycle_id] = measurement
            
        self._log_event('T1_image', cycle_id, data=f"{msg.width}x{msg.height}")
        rospy.logdebug(f"T1 - Image captured: {cycle_id}")
        
    def _on_gesture(self, msg):
        """T2: Handle hand gesture callback."""
        self.latest_gesture_value = msg.data
        
        # Use o carimbo do último frame da câmera para capture_ts
        if self.latest_image_timestamp is None:
            rospy.logwarn("Sem T1 ainda; ignorando gesto")
            return
            
        capture_ts = self.latest_image_timestamp         # mesmo do T1
        recv_ts = rospy.Time.now()                       # momento que recebemos o gesto
        
        # Find the most recent active cycle
        cycle_id = self._find_recent_cycle_for_timestamp(capture_ts)
        if cycle_id:
            with self.lock:
                if cycle_id in self.active_cycles:
                    m = self.active_cycles[cycle_id]
                    m.add_timestamp('T2_gesture', capture_ts, {
                        'gesture_value': msg.data
                    })
                    m.add_timestamp('T2_gesture_recv', recv_ts, {
                        'gesture_value': msg.data,
                        'recv_context': 'callback_entry'
                    })
                    
            self._log_event('T2_gesture', cycle_id, data=msg.data)
            rospy.logdebug(f"T2 - Gesture detected: {cycle_id}, value: {msg.data}")
            
            # Trigger finger count service if needed
            if msg.data == 1:  # Manual mode gesture
                self._call_finger_count_service(cycle_id)
                
    def _on_finger_count_result(self, msg):
        """T3: Handle finger count result from continuous_direct_grasp.py (debug only)."""
        timestamp = msg.stamp
        cycle_id = self._find_recent_cycle_for_timestamp(timestamp)
        
        # Log for debugging but don't save timestamps (service call handles that)
        if cycle_id:
            self._log_event('T3_finger_count_debug', cycle_id, data='detected_from_topic')
            rospy.logdebug(f"T3 - Finger count topic result: {cycle_id} (debug only)")
                
    def _call_finger_count_service(self, cycle_id):
        """T3: Call finger count service and measure response time."""
        if not self.finger_count_client:
            return
            
        def call_service():
            try:
                start_time = rospy.Time.now()
                response = self.finger_count_client()
                end_time = rospy.Time.now()
                
                with self.lock:
                    if cycle_id in self.active_cycles:
                        m = self.active_cycles[cycle_id]
                        m.add_timestamp('T3_finger_count_recv', end_time, {
                            'success': response.success,
                            'finger_count': response.message if response.success else 'failed',
                            'service_duration': (end_time - start_time).to_sec(),
                            'recv_context': 'service_response'
                        })
                        
                self._log_event('T3_finger_count', cycle_id, 
                               data=response.message if response.success else 'failed')
                rospy.logdebug(f"T3 - Finger count: {cycle_id}, result: {response.message}")
                
            except rospy.ServiceException as e:
                rospy.logwarn(f"Finger count service call failed: {e}")
                
        # Call service in a separate thread to avoid blocking
        import threading
        threading.Thread(target=call_service, daemon=True).start()
        
    def _on_tf(self, msg):
        """T4a: Handle TF broadcasts (looking for wrist frame)."""
        for transform in msg.transforms:
            if transform.child_frame_id == 'wrist':
                timestamp = transform.header.stamp
                cycle_id = self._find_recent_cycle_for_timestamp(timestamp)
                
                if cycle_id:
                    with self.lock:
                        if cycle_id in self.active_cycles:
                            self.active_cycles[cycle_id].add_timestamp('T4a_wrist_tf', timestamp, {
                                'frame': transform.child_frame_id,
                                'parent_frame': transform.header.frame_id
                            })
                            
                    self._log_event('T4a_wrist_tf', cycle_id, data='wrist')
                    rospy.logdebug(f"T4a - Wrist TF: {cycle_id}")
                break
                
    def _on_yolo_detection(self, msg):
        """T4b: Handle YOLO object detection."""
        timestamp = msg.header.stamp
        cycle_id = self._find_recent_cycle_for_timestamp(timestamp)
        
        if cycle_id:
            with self.lock:
                if cycle_id in self.active_cycles:
                    self.active_cycles[cycle_id].add_timestamp('T4b_yolo', timestamp, {
                        'object_class': msg.object_class,
                        'confidence': msg.confidence
                    })
                    
            self._log_event('T4b_yolo', cycle_id, data=f"{msg.object_class}:{msg.confidence}")
            rospy.logdebug(f"T4b - YOLO detection: {cycle_id}, {msg.object_class}")
            
    def _on_spot_command(self, msg):
        """T5: Handle Spot command sent."""
        capture_like = msg.header.stamp                  # timestamp da mensagem (referência)
        recv_ts = rospy.Time.now()                       # momento que recebemos no logger
        
        cycle_id = self._find_recent_cycle_for_timestamp(capture_like)
        
        if cycle_id:
            with self.lock:
                if cycle_id in self.active_cycles:
                    m = self.active_cycles[cycle_id]
                    m.add_timestamp('T5_command', capture_like, {
                        'command_type': msg.command_type
                    })
                    m.add_timestamp('T5_command_recv', recv_ts, {
                        'command_type': msg.command_type,
                        'recv_context': 'callback_entry'
                    })
                    
            self._log_event('T5_command', cycle_id, data=msg.command_type)
            rospy.logdebug(f"T5 - Spot command: {cycle_id}, {msg.command_type}")
            
    def _on_spot_feedback(self, msg):
        """T6: Handle Spot execution feedback."""
        capture_like = msg.header.stamp                  # timestamp da mensagem (referência)
        recv_ts = rospy.Time.now()                       # momento que recebemos no logger
        
        cycle_id = self._find_recent_cycle_for_timestamp(capture_like)
        
        if cycle_id:
            with self.lock:
                if cycle_id in self.active_cycles:
                    m = self.active_cycles[cycle_id]
                    m.add_timestamp('T6_feedback', capture_like, {
                        'success': msg.success,
                        'message': msg.message
                    })
                    m.add_timestamp('T6_feedback_recv', recv_ts, {
                        'success': msg.success,
                        'message': msg.message,
                        'recv_context': 'callback_entry'
                    })
                    
                    # Mark cycle as completed if all required data is available
                    if m.is_complete():
                        m.completed = True
                        self.completed_cycles.append(self.active_cycles.pop(cycle_id))
                        
            self._log_event('T6_feedback', cycle_id, data=f"success:{msg.success}")
            rospy.logdebug(f"T6 - Spot feedback: {cycle_id}, success: {msg.success}")
            
    def _find_recent_cycle_for_timestamp(self, timestamp):
        """Find the most recent active cycle for a given timestamp."""
        with self.lock:
            # Look for cycles within a reasonable time window (e.g., 2 seconds)
            max_age = rospy.Duration(5.0)
            best_cycle = None
            best_time_diff = float('inf')
            
            for cycle_id, measurement in self.active_cycles.items():
                if 'T1_image' in measurement.timestamps:
                    time_diff = abs((timestamp - measurement.timestamps['T1_image']).to_sec())
                    if time_diff < max_age.to_sec() and time_diff < best_time_diff:
                        best_cycle = cycle_id
                        best_time_diff = time_diff
                        
            return best_cycle
            
    def _cleanup_old_cycles(self, event):
        """Remove old incomplete cycles."""
        current_time = rospy.Time.now()
        max_age = rospy.Duration(self.max_cycle_age)
        
        with self.lock:
            cycles_to_remove = []
            for cycle_id, measurement in self.active_cycles.items():
                if 'T1_image' in measurement.timestamps:
                    age = current_time - measurement.timestamps['T1_image']
                    if age > max_age:
                        cycles_to_remove.append(cycle_id)
                        
            for cycle_id in cycles_to_remove:
                rospy.logwarn(f"Removing incomplete cycle: {cycle_id}")
                del self.active_cycles[cycle_id]
                
    def _save_completed_cycles(self, event):
        """Save completed cycles to CSV."""
        with self.lock:
            cycles_to_save = list(self.completed_cycles)
            self.completed_cycles.clear()
            
        for measurement in cycles_to_save:
            self._write_measurement_to_csv(measurement)
            
        # Flush files
        for csv_file in self.csv_files.values():
            csv_file.flush()
            
    def _write_measurement_to_csv(self, measurement):
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
        
        # Determine mode (manual vs semi-autonomous)
        mode = 'manual' if finger_count in ['1', '2'] else 'unknown'
        
        row = [
            measurement.cycle_id,
            timestamps.get('T1_image', rospy.Time(0)).to_sec(),
            mode,
            timestamps.get('T1_image', rospy.Time(0)).to_sec(),
            timestamps.get('T2_gesture', rospy.Time(0)).to_sec(),
            timestamps.get('T4a_wrist_tf', rospy.Time(0)).to_sec(),
            timestamps.get('T4b_yolo', rospy.Time(0)).to_sec(),
            timestamps.get('T5_command', rospy.Time(0)).to_sec(),
            timestamps.get('T6_feedback', rospy.Time(0)).to_sec(),
            timestamps.get('T1_image_recv', rospy.Time(0)).to_sec(),
            timestamps.get('T2_gesture_recv', rospy.Time(0)).to_sec(),
            timestamps.get('T3_finger_count_recv', rospy.Time(0)).to_sec(),
            timestamps.get('T5_command_recv', rospy.Time(0)).to_sec(),
            timestamps.get('T6_feedback_recv', rospy.Time(0)).to_sec(),
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
        
        self.csv_writers['latencies'].writerow(row)
        rospy.loginfo(f"Saved cycle {measurement.cycle_id}: total_latency={latencies['total_latency']:.3f}s")
        
    def shutdown(self):
        """Clean shutdown."""
        rospy.loginfo("Shutting down latency logger...")
        
        # Save any remaining completed cycles
        self._save_completed_cycles(None)
        
        # Close CSV files
        for csv_file in self.csv_files.values():
            csv_file.close()
            
        rospy.loginfo("Latency logger shutdown complete.")


def main():
    """Main entry point."""
    try:
        logger = LatencyLogger()
        
        # Register shutdown handler
        rospy.on_shutdown(logger.shutdown)
        
        rospy.loginfo("Latency logger started. Waiting for pipeline events...")
        rospy.spin()
        
    except rospy.ROSInterruptException:
        pass
    except Exception as e:
        rospy.logerr(f"Latency logger failed: {e}")
        raise


if __name__ == '__main__':
    main()
