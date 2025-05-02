#!/usr/bin/env python3
import rospy
import moveit_commander
from moveit_msgs.msg import JointConstraint, Constraints
from geometry_msgs.msg import PoseStamped
import subprocess
from std_msgs.msg import Int32

import bosdyn.client
import bosdyn.client.util
from bosdyn.client.robot_command import RobotCommandBuilder, RobotCommandClient
from bosdyn.client.robot_state import RobotStateClient
from bosdyn.client.frame_helpers import ODOM_FRAME_NAME, get_a_tform_b
from bosdyn.client.math_helpers import SE3Pose, Quat
from bosdyn.client.lease import LeaseClient, LeaseWallet, add_lease_wallet_processors, LeaseKeepAlive
from bosdyn.client.lease import ResourceAlreadyClaimedError

import tf2_ros
import tf2_geometry_msgs
from geometry_msgs.msg import TransformStamped

# Global variable to track the current gesture
gesture = 0

def gesture_callback(msg):
    global gesture
    gesture = msg.data


def get_simulated_end_effector_pose(group):
    """
    Lê a pose atual do end-effector da simulação usando MoveIt.
    """
    rospy.sleep(0.1)  # Pequena pausa para garantir atualização
    return group.get_current_pose().pose


def apply_wrist_lock(group, joint_name="arm_wr0"):
    """
    Trava a junta `joint_name` no valor atual, sem folga.
    """
    names = group.get_active_joints()
    vals  = group.get_current_joint_values()

    idx_wr0 = names.index("arm_wr0")
    locked_value_wr0 = vals[idx_wr0]
    rospy.loginfo("🔒 Travando arm_wr0 em %.3f rad", locked_value_wr0)
    jc_wr0 = JointConstraint(joint_name="arm_wr0",
                             position=locked_value_wr0,
                             tolerance_above=0.0,
                             tolerance_below=0.0,
                             weight=1.0)
    idx_wr1 = names.index("arm_wr1")
    locked_value_wr1 = vals[idx_wr1]
    rospy.loginfo("🔒 Travando arm_wr1 em %.3f rad", locked_value_wr1)
    jc_wr1 = JointConstraint(joint_name="arm_wr1",
                             position=locked_value_wr1,
                             tolerance_above=0.0,
                             tolerance_below=0.0,
                             weight=1.0)
    cs = Constraints()
    cs.joint_constraints.extend([jc_wr0, jc_wr1])
    group.set_path_constraints(cs)


def get_tf_pose(tf_buffer, target_frame="wrist", reference_frame="world"):
    """
    Obtém a pose do frame `target_frame` em relação ao `reference_frame` usando TF.
    """
    try:
        transform = tf_buffer.lookup_transform(reference_frame, target_frame, rospy.Time(0), rospy.Duration(1.0))
        pose = PoseStamped()
        pose.header = transform.header
        pose.pose.position.x = transform.transform.translation.x
        pose.pose.position.y = transform.transform.translation.y
        pose.pose.position.z = transform.transform.translation.z
        pose.pose.orientation = transform.transform.rotation
        return pose.pose
    except Exception as e:
        rospy.logwarn("❗ TF lookup failed: %s", e)
        return None


def main():
    rospy.init_node("continuous_moveit_pose_to_spot_real", anonymous=True)
    rospy.Subscriber("/hand_gesture", Int32, gesture_callback)

    tf_buffer = tf2_ros.Buffer()
    tf_listener = tf2_ros.TransformListener(tf_buffer)

    # Inicializa o MoveIt
    moveit_commander.roscpp_initialize([])
    group = moveit_commander.MoveGroupCommander("manipulator")
    group.set_end_effector_link("arm_link_fngr")
    rospy.loginfo("Simulação: End-effector (%s) em relação a: %s",
                  group.get_end_effector_link(), group.get_pose_reference_frame())

    apply_wrist_lock(group)

    # Conecta ao Spot real
    spot_hostname = rospy.get_param("~spot_hostname", "192.168.80.3")
    sdk = bosdyn.client.create_standard_sdk("ContinuousPoseToSpot")
    robot = sdk.create_robot(spot_hostname)
    robot.authenticate("admin", "spotadmin2017")
    robot.time_sync.wait_for_sync()

    if not robot.has_arm():
        rospy.logerr("Spot não possui braço. Abortando.")
        return 1

    # Inicializa os clientes
    command_client     = robot.ensure_client(RobotCommandClient.default_service_name)
    robot_state_client = robot.ensure_client(RobotStateClient.default_service_name)
    lease_client       = robot.ensure_client(LeaseClient.default_service_name)

    # Attempt to acquire the root lease, fallback to take() if already claimed
    try:
        root_lease = lease_client.acquire()
    except ResourceAlreadyClaimedError:
        rospy.logwarn("Lease already claimed; using take() to force acquisition.")
        root_lease = lease_client.take()

    # Setup wallet + processors
    lease_wallet = LeaseWallet()
    add_lease_wallet_processors(command_client, lease_wallet)
    lease_wallet.add(root_lease)

    # Keep lease alive (passando o wallet)
    lease_keepalive = LeaseKeepAlive(lease_client, lease_wallet,
                                    must_acquire=True, return_at_exit=False)

    rospy.loginfo("Conectado ao Spot real. Iniciando sincronização contínua...")
    with lease_keepalive:
        robot.power_on(timeout_sec=20)
        continuous_send_pose(spot_hostname, group, command_client, robot_state_client, tf_buffer)


def continuous_send_pose(spot_hostname, group, command_client, robot_state_client, tf_buffer):
    rate = rospy.Rate(2)
    while not rospy.is_shutdown():
        global gesture
        if gesture == 1:
            rospy.loginfo("✋ Gesto de agarrar detectado!")
            subprocess.run([
                "python3",
                "/root/ws_moveit/src/spot_operation/scripts/arm_grasp_yolo.py",
                "-v",
                "--use-wallet",
                "--force-top-down-grasp",
                spot_hostname
            ], check=False)
            gesture = 0
            rospy.sleep(2.0)
            continue

        sim_pose = get_tf_pose(tf_buffer)
        if sim_pose is None:
            rospy.logwarn("⚠️ Não foi possível obter a pose do wrist.")
            rate.sleep()
            continue

        robot_state = robot_state_client.get_robot_state()
        odom_T_body = get_a_tform_b(robot_state.kinematic_state.transforms_snapshot,
                                    ODOM_FRAME_NAME, "body")
        flat_body_T_hand = SE3Pose(
            x=sim_pose.position.x,
            y=sim_pose.position.y,
            z=sim_pose.position.z,
            rot=Quat(w=sim_pose.orientation.w,
                     x=sim_pose.orientation.x,
                     y=sim_pose.orientation.y,
                     z=sim_pose.orientation.z)
        )
        odom_T_hand = odom_T_body * flat_body_T_hand
        arm_command = RobotCommandBuilder.arm_pose_command(
            odom_T_hand.x, odom_T_hand.y, odom_T_hand.z,
            odom_T_hand.rot.w, odom_T_hand.rot.x,
            odom_T_hand.rot.y, odom_T_hand.rot.z,
            ODOM_FRAME_NAME, 0.5
        )
        command_client.robot_command(arm_command)
        rospy.loginfo("Comando enviado: Pose alvo = [%.3f, %.3f, %.3f]",
                      odom_T_hand.x, odom_T_hand.y, odom_T_hand.z)
        rate.sleep()

if __name__ == "__main__":
    main()
