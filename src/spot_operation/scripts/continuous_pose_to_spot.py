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
from bosdyn.client.lease import LeaseWallet, add_lease_wallet_processors

gesture = 0  # Global variable to track the current gesture

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
    # 1) lê nomes e valores atuais (troca get_joint_names → get_active_joints)
    names = group.get_active_joints()
    vals  = group.get_current_joint_values()

    # Trava a junta arm_wr0
    idx_wr0 = names.index("arm_wr0")
    locked_value_wr0 = vals[idx_wr0]
    rospy.loginfo("🔒 Travando arm_wr0 em %.3f rad", locked_value_wr0)

    jc_wr0 = JointConstraint()
    jc_wr0.joint_name      = "arm_wr0"
    jc_wr0.position        = locked_value_wr0
    jc_wr0.tolerance_above = 0.0
    jc_wr0.tolerance_below = 0.0
    jc_wr0.weight          = 1.0

    # Trava a junta arm_wr1
    idx_wr1 = names.index("arm_wr1")
    locked_value_wr1 = vals[idx_wr1]
    rospy.loginfo("🔒 Travando arm_wr1 em %.3f rad", locked_value_wr1)

    jc_wr1 = JointConstraint()
    jc_wr1.joint_name      = "arm_wr1"
    jc_wr1.position        = locked_value_wr1
    jc_wr1.tolerance_above = 0.0
    jc_wr1.tolerance_below = 0.0
    jc_wr1.weight          = 1.0

    # Aplica no planner
    cs = Constraints()
    cs.joint_constraints.append(jc_wr0)
    cs.joint_constraints.append(jc_wr1)
    group.set_path_constraints(cs)

def main():
    rospy.init_node("continuous_moveit_pose_to_spot_real", anonymous=True)
    rospy.Subscriber("/hand_gesture", Int32, gesture_callback)

    # Inicializa o MoveIt
    moveit_commander.roscpp_initialize([])
    group = moveit_commander.MoveGroupCommander("manipulator")
    group.set_end_effector_link("arm_link_fngr")
    rospy.loginfo("Simulação: End-effector (%s) em relação a: %s", 
                  group.get_end_effector_link(), group.get_pose_reference_frame())

    # Aplica trava de rotação na junta wr0
    apply_wrist_lock(group, "arm_wr0")

    # Conecta ao Spot real
    spot_hostname = rospy.get_param("~spot_hostname", "192.168.80.3")
    sdk = bosdyn.client.create_standard_sdk("ContinuousPoseToSpot")
    robot = sdk.create_robot(spot_hostname)
    robot.authenticate("admin", "spotadmin2017")
    robot.time_sync.wait_for_sync()

    if not robot.has_arm():
        rospy.logerr("Spot não possui braço. Abortando.")
        return 1

    # Inicializa os clientes do Spot
    command_client      = robot.ensure_client(RobotCommandClient.default_service_name)
    robot_state_client  = robot.ensure_client(RobotStateClient.default_service_name)
    lease_client        = robot.ensure_client(bosdyn.client.lease.LeaseClient.default_service_name)

    # Configure LeaseWallet
    lease_wallet = LeaseWallet()
    add_lease_wallet_processors(command_client, lease_wallet)

    # Acquire the first lease and add it to the wallet
    lease = lease_client.take()
    lease_wallet.add(lease)

    rospy.loginfo("Conectado ao Spot real. Iniciando sincronização contínua...")
    with bosdyn.client.lease.LeaseKeepAlive(lease_client, must_acquire=True, return_at_exit=False):
        robot.power_on(timeout_sec=20)
        continuous_send_pose(spot_hostname, group, command_client, robot_state_client)

def continuous_send_pose(spot_hostname, group, command_client, robot_state_client):
    rate = rospy.Rate(2)  # Atualiza 2 Hz (ajuste conforme necessário)

    while not rospy.is_shutdown():
        global gesture

        # Check for gesture 1 to trigger grasp
        if gesture == 1:
            rospy.loginfo("✋ Gesto de agarrar detectado!")
            try:
                result = subprocess.run([
                    "python3",
                    "/root/ws_moveit/src/spot_operation/scripts/arm_grasp_yolo.py",
                    "-v",
                    # "--use-wallet",
                    spot_hostname
                ], check=False)

                if result.returncode != 0:
                    rospy.logwarn("⚠️ Grasp falhou com código: %d", result.returncode)
                else:
                    rospy.loginfo("✅ Grasp concluído com sucesso.")

            except Exception as e:
                rospy.logwarn("⚠️ Grasp interrompido por exceção: %s", str(e))

            # Reset gesture to 0 after grasp
            gesture = 0

            # Wait for Spot to stabilize before resuming
            rospy.sleep(2.0)
            continue

        # 1. Obtém a pose do end-effector na simulação.
        sim_pose = get_simulated_end_effector_pose(group)

        # 2. Lê a transformação atual do Spot: de ODOM para o corpo (gravity-aligned)
        robot_state = robot_state_client.get_robot_state()
        odom_T_body = get_a_tform_b(robot_state.kinematic_state.transforms_snapshot,
                                    ODOM_FRAME_NAME, "body")

        # 3. Constrói a pose do end-effector em relação ao corpo
        flat_body_T_hand = SE3Pose(
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

        # 4. Converte a pose para o frame global (odom)
        odom_T_hand = odom_T_body * flat_body_T_hand

        # 5. Cria o comando de movimento com uma duração curta
        seconds = 0.5
        arm_command = RobotCommandBuilder.arm_pose_command(
            odom_T_hand.x, odom_T_hand.y, odom_T_hand.z,
            odom_T_hand.rot.w, odom_T_hand.rot.x, odom_T_hand.rot.y, odom_T_hand.rot.z,
            ODOM_FRAME_NAME, seconds
        )

        # 6. Envia o comando
        command_client.robot_command(arm_command)
        rospy.loginfo("Comando enviado: Pose alvo (odom) = [%.3f, %.3f, %.3f]", 
                      odom_T_hand.x, odom_T_hand.y, odom_T_hand.z)

        rate.sleep()

if __name__ == "__main__":
    main()
