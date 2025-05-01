### continuous_pose_to_spot.py
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


def main():
    rospy.init_node("continuous_moveit_pose_to_spot_real", anonymous=True)
    rospy.Subscriber("/hand_gesture", Int32, gesture_callback)

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
        continuous_send_pose(spot_hostname, group, command_client, robot_state_client)


def continuous_send_pose(spot_hostname, group, command_client, robot_state_client):
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

        sim_pose = get_simulated_end_effector_pose(group)
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


### arm_object_grasp_yolo.py
#!/usr/bin/env python3
import argparse
import time
import cv2
import numpy as np
import pandas as pd
from ultralytics import YOLO

import bosdyn.client
import bosdyn.client.util
from bosdyn.api import geometry_pb2, image_pb2, manipulation_api_pb2
from bosdyn.client.estop import EstopClient
from bosdyn.client.frame_helpers import VISION_FRAME_NAME, get_vision_tform_body, get_a_tform_b, math_helpers
from bosdyn.client.image import ImageClient
from bosdyn.client.manipulation_api_client import ManipulationApiClient
from bosdyn.client.robot_command import RobotCommandClient
from bosdyn.client.robot_state import RobotStateClient
from bosdyn.client.lease import LeaseClient, LeaseWallet, add_lease_wallet_processors, LeaseKeepAlive


def arm_object_grasp(config):
    bosdyn.client.util.setup_logging(config.verbose)
    sdk = bosdyn.client.create_standard_sdk('ArmObjectGraspYOLO')
    robot = sdk.create_robot(config.hostname)
    robot.authenticate("admin", "spotadmin2017")
    robot.time_sync.wait_for_sync()

    cmd_client           = robot.ensure_client(RobotCommandClient.default_service_name)
    manipulation_client  = robot.ensure_client(ManipulationApiClient.default_service_name)
    image_client         = robot.ensure_client(ImageClient.default_service_name)
    robot_state_client   = robot.ensure_client(RobotStateClient.default_service_name)
    lease_client         = robot.ensure_client(LeaseClient.default_service_name)

    # 1) Acquire root lease
    lease = lease_client.acquire()
    # 2) Setup wallet & processors
    lease_wallet = LeaseWallet()
    add_lease_wallet_processors(cmd_client, lease_wallet)
    add_lease_wallet_processors(manipulation_client, lease_wallet)
    # 3) Add lease
    lease_wallet.add(lease)

    # 4) Keep alive & execute grasp
    with LeaseKeepAlive(lease_client, must_acquire=True, return_at_exit=False):
        # Load model & CSV
        allowed_df = pd.read_csv(config.allowed_csv)
        allowed_df['class'] = allowed_df['class'].str.strip().str.lower()
        yolo = YOLO(config.yolo_model)

        # Capture image
        img_resp = image_client.get_image_from_sources([config.image_source])[0]
        arr = np.frombuffer(img_resp.shot.image.data,
                            dtype=(np.uint16 if img_resp.shot.image.pixel_format == image_pb2.Image.PIXEL_FORMAT_DEPTH_U16 else np.uint8))
        img = (arr.reshape(img_resp.shot.image.rows, img_resp.shot.image.cols)
               if img_resp.shot.image.format == image_pb2.Image.FORMAT_RAW else cv2.imdecode(arr, -1))

        # YOLO inference
        results = yolo(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        boxes = results[0].boxes.xyxy.cpu().numpy()
        classes = results[0].boxes.cls.cpu().numpy().astype(int)
        confs = results[0].boxes.conf.cpu().numpy()
        names = [results[0].names[c].lower() for c in classes]

        # Filter & select
        filtered = []
        for i,name in enumerate(names):
            df = allowed_df[allowed_df['class']==name]
            if not df.empty:
                pr = int(df['priority'].iloc[0])
                x1,y1,x2,y2 = boxes[i]
                filtered.append((pr, -(x2-x1)*(y2-y1), i))
        filtered.sort()
        _,_,sel = filtered[0]
        cx = int((boxes[sel][0]+boxes[sel][2])/2)
        cy = int((boxes[sel][1]+boxes[sel][3])/2)

        pick = manipulation_api_pb2.PickObjectInImage(
            pixel_xy=geometry_pb2.Vec2(x=cx,y=cy),
            transforms_snapshot_for_camera=img_resp.shot.transforms_snapshot,
            frame_name_image_sensor=img_resp.shot.frame_name_image_sensor,
            camera_model=img_resp.source.pinhole)

        req = manipulation_api_pb2.ManipulationApiRequest(pick_object_in_image=pick)
        cmd_resp = manipulation_client.manipulation_api_command(req)

        # Feedback loop
        while True:
            fb = manipulation_api_pb2.ManipulationApiFeedbackRequest(
                manipulation_cmd_id=cmd_resp.manipulation_cmd_id)
            resp = manipulation_client.manipulation_api_feedback_command(fb)
            st = manipulation_api_pb2.ManipulationFeedbackState.Name(resp.current_state)
            print(f"Current state: {st}")
            if resp.current_state in (
                manipulation_api_pb2.MANIP_STATE_GRASP_SUCCEEDED,
                manipulation_api_pb2.MANIP_STATE_GRASP_FAILED):
                break
            time.sleep(0.25)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('-v','--verbose',action='store_true')
    p.add_argument('hostname',help='Spot hostname')
    p.add_argument('-i','--image-source',default='hand_color_image')
    p.add_argument('--yolo-model',default='yolo11n.pt')
    p.add_argument('--force-top-down-grasp', action='store_true')
    p.add_argument('--force-horizontal-grasp', action='store_true')
    p.add_argument('--force-45-angle-grasp', action='store_true')
    p.add_argument('--force-squeeze-grasp', action='store_true')
    p.add_argument('--allowed-csv', default='/root/ws_moveit/src/spot_operation/config/allowed_objects.csv')
    cfg = p.parse_args()
    arm_object_grasp(cfg)

if __name__=='__main__':
    main()
