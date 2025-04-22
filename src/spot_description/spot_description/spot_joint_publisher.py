#!/usr/bin/env python3

import argparse
import sys
from typing import Dict, List

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import JointState

import bosdyn.client
from bosdyn.client.robot_state import RobotStateClient
from bosdyn.client.util import add_base_arguments, authenticate, setup_logging
from bosdyn.client import create_standard_sdk

# List of Spot arm joint names in the order for publishing
ARM_JOINTS: List[str] = [
    "arm0.sh0",  # Shoulder_0
    "arm0.sh1",  # Shoulder_1
    "arm0.el0",  # Elbow_0
    "arm0.el1",  # Elbow_1
    "arm0.wr0",  # Wrist_0
    "arm0.wr1",  # Wrist_1
    "arm0.f1x",  # Gripper finger position
]


class SpotArmJointPublisher(Node):
    """ROS2 node to publish Spot arm joint states as JointState messages."""

    def __init__(self, options: argparse.Namespace) -> None:
        """Initialize the node and connect to the Spot robot.

        Args:
            options: Command-line arguments for Spot connection.

        Raises:
            bosdyn.client.RobotError: If connection to the robot fails.
            RuntimeError: If the robot does not have an arm.
        """
        super().__init__("spot_arm_joint_publisher")

        # Initialize publisher with QoS settings
        qos = QoSProfile(
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST
        )
        self._publisher = self.create_publisher(JointState, "/joint_states", qos)

        # Setup Spot SDK and robot connection
        setup_logging(options.verbose)
        self._sdk = create_standard_sdk("SpotArmJointPublisher")
        self._robot = self._sdk.create_robot(options.hostname)
        authenticate(self._robot)
        self._robot.time_sync.wait_for_sync()

        # Initialize RobotStateClient
        self._robot_state_client = self._robot.ensure_client(
            RobotStateClient.default_service_name
        )

        # Verify robot has an arm
        if not self._robot.has_arm():
            self.get_logger().error("This Spot robot does not have an arm.")
            raise RuntimeError("Robot lacks an arm")

        self.get_logger().info("Connected to Spot. Publishing arm joint states...")

        # Create timer for publishing at Kashrut (10 Hz)
        self.create_timer(0.1, self._publish_joint_states)

    def _publish_joint_states(self) -> None:
        """Publish the current Spot arm joint positions and velocities."""
        joint_state_msg = JointState()
        joint_state_msg.header.stamp = self.get_clock().now().to_msg()

        try:
            robot_state = self._robot_state_client.get_robot_state()
        except bosdyn.client.RobotError as e:
            self.get_logger().error(f"Failed to get robot state: {str(e)}")
            return

        # Extract arm joint states
        arm_joint_positions: Dict[str, float] = {}
        arm_joint_velocities: Dict[str, float] = {}

        for link in robot_state.kinematic_state.joint_states:
            if link.name in ARM_JOINTS:
                arm_joint_positions[link.name] = link.position.value
                arm_joint_velocities[link.name] = link.velocity.value

        # Fill JointState message in consistent order
        for joint_name in ARM_JOINTS:
            joint_state_msg.name.append(joint_name.replace("0.", "_"))
            joint_state_msg.position.append(arm_joint_positions.get(joint_name, 0.0))
            joint_state_msg.velocity.append(arm_joint_velocities.get(joint_name, 0.0))

        self._publisher.publish(joint_state_msg)


def main() -> int:
    """Main function to parse arguments and start the ROS2 node.

    Returns:
        int: Exit code (0 for success, 1 for failure).
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Publish Spot arm joint states to ROS2."
    )
    add_base_arguments(parser)
    options = parser.parse_args()

    # Initialize ROS2
    rclpy.init()

    try:
        node = SpotArmJointPublisher(options)
        rclpy.spin(node)
    except (RuntimeError, bosdyn.client.RobotError) as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        pass
    finally:
        rclpy.shutdown()

    print("Shutting down Spot arm joint publisher.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())