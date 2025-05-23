#!/usr/bin/env python3

import sys
import rospy
import bosdyn.client
import bosdyn.client.util
from bosdyn.client.robot_state import RobotStateClient
import moveit_commander

SPOT_HOSTNAME = "192.168.80.3"
SPOT_USERNAME = "admin"
SPOT_PASSWORD = "spotadmin2017"

ARM_JOINTS = [
    "arm0.sh0", "arm0.sh1", "arm0.el0",
    "arm0.el1", "arm0.wr0", "arm0.wr1"
]
MOVEIT_JOINTS = [
    "arm_sh0", "arm_sh1", "arm_el0",
    "arm_el1", "arm_wr0", "arm_wr1"
]

TOLERANCE = 0.01

def has_significant_difference(state1, state2):
    for j in state1:
        if abs(state1[j] - state2.get(j, 0.0)) > TOLERANCE:
            return True
    return False

def main():
    rospy.init_node("sync_spot_arm_to_moveit", anonymous=True)
    moveit_commander.roscpp_initialize(sys.argv)
    group = moveit_commander.MoveGroupCommander("manipulator")

    bosdyn.client.util.setup_logging()
    sdk = bosdyn.client.create_standard_sdk("SpotArmSync")
    robot = sdk.create_robot(SPOT_HOSTNAME)
    robot.authenticate(SPOT_USERNAME, SPOT_PASSWORD)
    robot.time_sync.wait_for_sync()
    state_client = robot.ensure_client(RobotStateClient.default_service_name)

    rospy.loginfo("Conectado ao Spot. Sincronizando juntas com MoveIt...")

    last_joint_dict = None
    rate = rospy.Rate(5)

    while not rospy.is_shutdown():
        try:
            robot_state = state_client.get_robot_state()
        except Exception as e:
            rospy.logerr(f"Erro ao obter estado do Spot: {e}")
            rate.sleep()
            continue

        joint_pos = {}
        for joint in robot_state.kinematic_state.joint_states:
            if joint.name in ARM_JOINTS:
                joint_pos[joint.name] = joint.position.value

        joint_values = [joint_pos.get(j, 0.0) for j in ARM_JOINTS]
        joint_dict = dict(zip(MOVEIT_JOINTS, joint_values))

        if last_joint_dict is None or has_significant_difference(joint_dict, last_joint_dict):
            try:
                group.set_joint_value_target(joint_dict)
                group.go(wait=False)
                last_joint_dict = joint_dict.copy()
            except Exception as e:
                rospy.logwarn(f"Erro ao mover o grupo: {e}")

        rate.sleep()

if __name__ == '__main__':
    main()