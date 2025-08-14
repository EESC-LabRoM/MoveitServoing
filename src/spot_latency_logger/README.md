# Spot Teleoperation Latency Measurement System

## Overview

This package provides comprehensive latency measurement for the Spot teleoperation pipeline, tracking timing from image capture through perception, decision-making, and action execution.

## Pipeline Stages Measured

- **T1**: Camera image capture (`/camera/color/image_raw`)
- **T2**: Hand gesture detection (`/hand_gesture`)
- **T3**: Finger count service response (manual/semi-auto mode selection)
- **T4a**: Wrist TF broadcast (`/tf` with `wrist` frame)
- **T4b**: YOLO object detection (`/yolo/detection`)
- **T5**: Spot command sent (`/spot/cmd_sent`)
- **T6**: Spot execution feedback (`/spot/exec_done`)

## Quick Start

### 1. Build the Package

```bash
cd ~/ws_moveit
catkin build spot_latency_logger
source devel/setup.bash
```

### 2. Launch Complete System

```bash
roslaunch spot_latency_logger teleop_with_logger.launch
```

This single launch file starts:
- RealSense camera
- All hand/arm pose estimation nodes
- MoveIt planning
- Latency logger
- Spot teleoperation controller

### 3. Operate the System

1. **Mode Selection**: When prompted, show 1 or 2 fingers to select:
   - 1 finger = Manual mode
   - 2 fingers = Semi-autonomous mode

2. **Control Gestures**:
   - Open palm = Move arm to hand position
   - Closed fist = Hold position/grasp object

3. **Data Collection**: The system automatically logs all latency measurements to CSV files in `src/spot_latency_logger/logs/`

### 4. Analyze Results

```bash
# View summary statistics only
python3 src/spot_latency_logger/scripts/analyze_latency.py src/spot_latency_logger/logs --summary-only

# Generate full analysis report with plots
python3 src/spot_latency_logger/scripts/analyze_latency.py src/spot_latency_logger/logs
```

## Output Files

### CSV Files

1. **`spot_latencies_YYYYMMDD_HHMMSS.csv`**: Main latency measurements
   - Columns: cycle_id, timestamps (T1-T6), calculated latencies, metadata
   - One row per complete pipeline cycle

2. **`spot_events_YYYYMMDD_HHMMSS.csv`**: Detailed event log
   - All individual events with timestamps for debugging

### Analysis Reports

- **`latency_analysis_report_YYYYMMDD_HHMMSS.txt`**: Text summary statistics
- **`latency_distribution_YYYYMMDD_HHMMSS.png`**: Histogram plots
- **`latency_timeline_YYYYMMDD_HHMMSS.png`**: Latency over time
- **`mode_comparison_YYYYMMDD_HHMMSS.png`**: Manual vs semi-auto comparison

## Configuration

### Launch Parameters

```xml
<!-- Latency logger parameters -->
<param name="output_dir" value="/path/to/logs"/>           <!-- Default: src/spot_latency_logger/logs -->
<param name="max_cycle_age_sec" value="10.0"/>             <!-- Default: 10.0 seconds -->
<param name="buffer_size" value="100"/>                    <!-- Default: 100 cycles -->

<!-- Spot controller parameters -->
<param name="spot_hostname" value="192.168.80.3"/>        <!-- Spot IP address -->
<param name="model_path" value="/path/to/yolo.pt"/>        <!-- YOLO model file -->
```

## Measured Latencies

- **Perception Latency**: T2 - T1 (image → gesture detection)
- **Decision Latency**: T5 - T2 (gesture → command decision)
- **Execution Latency**: T6 - T5 (command → feedback)
- **Total Latency**: T6 - T1 (end-to-end)
- **Finger Count Latency**: T3 - T2 (service response time)
- **Wrist TF Latency**: T4a - T1 (pose estimation)
- **YOLO Detection Latency**: T4b - T1 (object detection)

## Synchronization

The system uses ROS timestamps for temporal correlation:
- All nodes should use the same ROS master
- Ensure time synchronization across devices (NTP/chrony)
- Camera timestamps are used as the reference time base

## Troubleshooting

### Common Issues

1. **No latency measurements**:
   - Check that all nodes are publishing to the expected topics
   - Verify custom messages are built: `catkin build spot_latency_logger`

2. **Missing data in cycles**:
   - Some pipeline stages may be optional (T3, T4a, T4b)
   - Only T1, T2, T5, T6 are required for a complete measurement

3. **Time synchronization issues**:
   - Ensure all devices use the same time source
   - Check ROS time vs system time consistency

### Debug Topics

Monitor these topics to verify data flow:
```bash
rostopic echo /camera/color/image_raw                # T1
rostopic echo /hand_gesture                         # T2
rostopic echo /tf                                   # T4a
rostopic echo /yolo/detection                       # T4b
rostopic echo /spot/cmd_sent                        # T5
rostopic echo /spot/exec_done                       # T6
```

## Integration Notes

### Modifying Existing Nodes

The system requires minimal changes to existing nodes:

1. **`continuous_direct_grasp.py`**: Modified to publish `/spot/cmd_sent` and `/spot/exec_done`
2. **Other nodes**: No changes required, they already publish the monitored topics

### Adding New Measurements

To add new latency measurements:

1. Create new message types in `msg/`
2. Add subscribers in `latency_logger.py`
3. Update CSV headers and analysis scripts
4. Rebuild the package

## Performance Impact

The latency measurement system has minimal performance impact:
- Lightweight ROS message publishing
- Asynchronous CSV writing
- Optional analysis components

## Example Results

Typical latency ranges (varies by hardware and network):
- **Perception**: 50-200ms (camera processing + hand detection)
- **Decision**: 10-100ms (gesture interpretation + planning)
- **Execution**: 100-500ms (network + robot response)
- **Total**: 200-800ms (end-to-end pipeline)

## Dependencies

- ROS Noetic
- OpenCV
- MediaPipe
- Boston Dynamics Spot SDK
- YOLO (Ultralytics)
- Pandas, Matplotlib, Scipy (for analysis)

## Author

Created for Spot teleoperation research. For questions or improvements, please create an issue.
