#!/usr/bin/env python3

import argparse
import logging
import os
import sys
from typing import Optional
import time
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Pose
from moveit2 import MoveGroupInterface

import bosdyn.client
from bosdyn.client.lease import LeaseClient, LeaseKeepAlive
from bosdyn.client.robot_command import RobotCommandBuilder, RobotCommandClient
from bosdyn.client.robot_state import RobotStateClient
from bosdyn.client.util import add_base_arguments, authenticate, setup_logging
from bosdyn.client import create_standard_sdk
from bosdyn.client.frame_helpers import ODOM_FRAME_NAME, get_a_tform_b
from bosdyn.client.math_helpers import SE3Pose, Quat

# Constants
PUBLISH_RATE_HZ = 2  # Frequency for sending pose commands (Hz)
COMMAND_DURATION_SECONDS = 0.5  # Duration for each arm pose command
DEFAULT_SPOT_HOSTNAME = "192.168.80.3"
MOVEIT_GROUP_NAME = "manipulator"
END_EFFECTOR_LINK = "arm_link_fngr"


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments for Spot connection.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Synchronize simulated MoveIt poses to Spot's real arm in ROS2."
    )
    add_base_arguments(parser)
    parser.add_argument(
        "--spot-hostname",
        default=DEFAULT_SPOT_HOSTNAME,
        help="Hostname or IP address of the Spot robot.",
    )
    return parser.parse_args()


def get_simulated_end_effector_pose(node: Node, moveit_group: MoveGroupInterface) -> Optional[Pose]:
    """Retrieve the current end-effector pose from the MoveIt simulation.

    Args:
        node: ROS2 node for logging.
        moveit_group: MoveIt group interface for the manipulator.

    Returns:
        Optional[Pose]: Current end-effector pose, or None if retrieval fails.
    """
    # Small delay to ensure MoveIt updates (approximates original sleep)
    time.sleep(0.1)
    pose_stamped = moveit_group.get_current_pose()
    return pose_stamped.pose


class SpotArmPoseSynchronizer(Node):
    """ROS2 node to synchronize simulated MoveIt end-effector poses to Spot's real arm."""

    def __init__(self, options: argparse.Namespace) -> None:
        """Initialize the node, MoveIt, and Spot robot connection.

        Args:
            options: Command-line arguments for Spot connection.

        Raises:
            bosdyn.client.RobotError: If connection to Spot fails.
            RuntimeError: If the robot lacks an arm or MoveIt initialization fails.
        """
        super().__init__("spot_arm_pose_synchronizer")

        # Configure logging
        self._logger = logging.getLogger(__name__)

        # Initialize MoveIt
        self._moveit_group = MoveGroupInterface(
            node=self,
            group_name=MOVEIT_GROUP_NAME,
            end_effector_link=END_EFFECTOR_LINK
        )
        self._logger.info(
            f"MoveIt initialized: End-effector ({self._moveit_group.get_end_effector_link()}) "
            f"relative to {self._moveit_group.get_pose_reference_frame()}"
        )

        # Initialize Spot SDK and robot
        setup_logging(options.verbose)
        self._sdk = create_standard_sdk("SpotArmPoseSynchronizer")
        self._robot = self._sdk.create_robot(options.spot_hostname)
        
        # Authenticate using environment variables
        username = os.getenv("BOSDYN_CLIENT_USERNAME")
        password = os.getenv("BOSDYN_CLIENT_PASSWORD")
        if not (username and password):
            self._logger.error("Spot credentials not set in environment variables.")
            raise RuntimeError("Missing Spot credentials")
        authenticate(self._robot, username=username, password=password)
        self._robot.time_sync.wait_for_sync()

        # Verify robot has an arm
        if not self._robot.has_arm():
            self._logger.error("Spot robot does not have an arm.")
            raise RuntimeError("Robot lacks an arm")

        # Initialize Spot clients
        self._command_client = self._robot.ensure_client(RobotCommandClient.default_service_name)
        self._robot_state_client = self._robot.ensure_client(RobotStateClient.default_service_name)
        self._lease_client = self._robot.ensure_client(LeaseClient.default_service_name)

        # Take lease and power on robot
        self._lease_client.take()
        self._robot.power_on(timeout_sec=20)

        self._logger.info("Connected to Spot. Starting continuous pose synchronization...")

        # Create timer for continuous pose updates
        self._timer = self.create_timer(1.0 / PUBLISH_RATE_HZ, self._synchronize_pose)

        # Manage lease with context manager
        self._lease_keepalive = LeaseKeepAlive(self._lease_client, must_acquire=True)

    def __del__(self) -> None:
        """Clean up resources on node destruction."""
        if hasattr(self, "_lease_keepalive"):
            self._lease_keepalive.shutdown()

    def _synchronize_pose(self) -> None:
        """Read simulated pose, transform to Spot's odom frame, and send arm command."""
        # Get simulated pose
        sim_pose = get_simulated_end_effector_pose(self, self._moveit_group)
        if sim_pose is None:
            return

        try:
            # Get transformation from odom to body
            robot_state = self._robot_state_client.get_robot_state()
            odom_t_body = get_a_tform_b(
                robot_state.kinematic_state.transforms_snapshot, ODOM_FRAME_NAME, "body"
            )

            # Construct pose in body frame
            flat_body_t_hand = SE3Pose(
                x=sim_pose.position.x,
                y=sim_pose.position.y,
                z=sim_pose.position.z,
                rot=Quat(
                    w=sim_pose.orientation.w,
                    x=sim_pose.orientation.x,
                    y=sim_pose.orientation.y,
                    z=sim_pose.orientation.z
                )
            )

            # Transform to odom frame
            odom_t_hand = odom_t_body * flat_body_t_hand

            # Create and send arm command
            arm_command = RobotCommandBuilder.arm_pose_command(
                odom_t_hand.x,
                odom_t_hand.y,
                odom_t_hand.z,
                odom_t_hand.rot.w,
                odom_t_hand.rot.x,
                odom_t_hand.rot.y,
                odom_t_hand.rot.z,
                ODOM_FRAME_NAME,
                COMMAND_DURATION_SECONDS
            )
            self._command_client.robot_command(arm_command)
            self._logger.info(
                f"Command sent: Target pose (odom) = [{odom_t_hand.x:.3f}, "
                f"{odom_t_hand.y:.3f}, {odom_t_hand.z:.3f}]"
            )
        except bosdyn.client.RobotError as e:
            self._logger.error(f"Failed to process or send command: {str(e)}")


def main() -> int:
    """Main entry point for the Spot arm pose synchronizer.

    Returns:
        int: Exit code (0 for success, 1 for failure).
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)

    # Parse arguments
    options = parse_arguments()

    # Initialize ROS2
    rclpy.init()
    try:
        node = SpotArmPoseSynchronizer(options)
        rclpy.spin(node)
    except (RuntimeError, bosdyn.client.RobotError) as e:
        logger.error(f"Failed to run node: {str(e)}")
        return 1
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully.")
    finally:
        rclpy.shutdown()

    logger.info("Spot arm pose synchronizer shut down.")
    return 0


if __name__ == "__main__":
    sys.exit(main())