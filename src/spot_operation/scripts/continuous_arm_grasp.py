#!/usr/bin/env python3
import rospy
import moveit_commander
from moveit_msgs.msg import JointConstraint, Constraints
from std_msgs.msg import Int32

import subprocess
import cv2
import numpy as np
import pandas as pd
from ultralytics import YOLO

import bosdyn.client
from bosdyn.client.robot_command import RobotCommandBuilder, RobotCommandClient
from bosdyn.client.robot_state import RobotStateClient
from bosdyn.client.frame_helpers import ODOM_FRAME_NAME, get_a_tform_b
from bosdyn.client.math_helpers import SE3Pose, Quat
from bosdyn.client.lease import LeaseClient, LeaseKeepAlive
from bosdyn.client.manipulation_api_client import ManipulationApiClient
from bosdyn.client.image import ImageClient
from bosdyn.api import geometry_pb2, manipulation_api_pb2, image_pb2

# global
gesture = 0

def gesture_cb(msg):
    global gesture
    gesture = msg.data

def apply_wrist_lock(group):
    names = group.get_active_joints()
    vals = group.get_current_joint_values()
    constraints = []
    for joint in ["arm_wr0","arm_wr1"]:
        idx = names.index(joint)
        val = vals[idx]
        jc = JointConstraint(joint_name=joint, position=val,
                             tolerance_above=0.0, tolerance_below=0.0, weight=1.0)
        constraints.append(jc)
    cs = Constraints()
    cs.joint_constraints.extend(constraints)
    group.set_path_constraints(cs)

def do_yolo_grasp(robot, config):
    # preparar clients
    cmd_client = robot.ensure_client(RobotCommandClient.default_service_name)
    mani_client = robot.ensure_client(ManipulationApiClient.default_service_name)
    img_client = robot.ensure_client(ImageClient.default_service_name)
    state_client = robot.ensure_client(RobotStateClient.default_service_name)

    # carrega CSV e modelo
    allowed = pd.read_csv(config['csv'])
    allowed['class']=allowed['class'].str.strip().str.lower()
    yolo = YOLO(config['yolo_model'])

    # pega imagem
    resp = img_client.get_image_from_sources([config['image_source']])[0]
    arr = np.frombuffer(resp.shot.image.data, dtype=np.uint8)
    img = (arr.reshape(resp.shot.image.rows, resp.shot.image.cols) 
           if resp.shot.image.format==image_pb2.Image.FORMAT_RAW
           else cv2.imdecode(arr, -1))
    results = yolo(cv2.cvtColor(img,cv2.COLOR_BGR2RGB))
    boxes = results[0].boxes.xyxy.cpu().numpy()
    classes = results[0].boxes.cls.cpu().numpy().astype(int)
    names = [results[0].names[c].lower() for c in classes]
    # filtra e escolhe
    cand=[]
    for i,name in enumerate(names):
        df=allowed[allowed['class']==name]
        if df.empty: continue
        pr=int(df['priority'].iloc[0])
        x1,y1,x2,y2=boxes[i]
        cand.append((pr, -(x2-x1)*(y2-y1), i))

    if not cand:
        rospy.logwarn("[GRASP] Nenhum objeto permitido detectado na imagem.")
        return  # evita crash e deixa o loop continuar

    _,_,sel=cand[0]
    x1,y1,x2,y2=boxes[sel]
    cx,cy=int((x1+x2)/2), int((y1+y2)/2)

    # monta request
    pick=manipulation_api_pb2.PickObjectInImage(
        pixel_xy=geometry_pb2.Vec2(x=cx,y=cy),
        transforms_snapshot_for_camera=resp.shot.transforms_snapshot,
        frame_name_image_sensor=resp.shot.frame_name_image_sensor,
        camera_model=resp.source.pinhole)
    req=manipulation_api_pb2.ManipulationApiRequest(pick_object_in_image=pick)
    cmd_resp = mani_client.manipulation_api_command(req, timeout=5.0)

    # loop feedback
    while True:
        fb_req = manipulation_api_pb2.ManipulationApiFeedbackRequest(
            manipulation_cmd_id=cmd_resp.manipulation_cmd_id)
        fb = mani_client.manipulation_api_feedback_command(fb_req)
        state = manipulation_api_pb2.ManipulationFeedbackState.Name(fb.current_state)
        print(f"[GRASP] Estado = {state}")
        if fb.current_state in (
            manipulation_api_pb2.MANIP_STATE_GRASP_SUCCEEDED,
            manipulation_api_pb2.MANIP_STATE_GRASP_FAILED):
            break
        rospy.sleep(0.2)

def main():
    rospy.init_node("spot_moveit_yolo_node", anonymous=True)
    rospy.Subscriber("/hand_gesture", Int32, gesture_cb)

    # MoveIt
    moveit_commander.roscpp_initialize([])
    group = moveit_commander.MoveGroupCommander("manipulator")
    group.set_end_effector_link("arm_link_fngr")
    apply_wrist_lock(group)

    # Spot SDK
    host = rospy.get_param("~spot_hostname","192.168.80.3")
    sdk = bosdyn.client.create_standard_sdk("UnifiedNode")
    robot = sdk.create_robot(host)
    robot.authenticate("admin","spotadmin2017")
    robot.time_sync.wait_for_sync()

    if not robot.has_arm():
        rospy.logerr("Spot sem braço! Abortando.")
        return

    cmd_client = robot.ensure_client(RobotCommandClient.default_service_name)
    state_client = robot.ensure_client(RobotStateClient.default_service_name)
    lease_client = robot.ensure_client(LeaseClient.default_service_name)

    # adquiri lease (take) e keepalive
    lease = lease_client.take()
    keep = LeaseKeepAlive(lease_client, must_acquire=True, return_at_exit=False)
    rospy.loginfo("Lease tomado. Ligando robô e iniciando loop...")
    grasp_executado = False  # Flag to prevent multiple grasps
    with keep:
        robot.power_on(timeout_sec=20)
        rate = rospy.Rate(2)
        # config para grasp
        grasp_cfg = {
            'image_source': 'hand_color_image',
            'yolo_model': '/root/ws_moveit/src/spot_operation/scripts/yolo11n.pt',
            'csv': '/root/ws_moveit/src/spot_operation/config/allowed_objects.csv'
        }
        while not rospy.is_shutdown():
            global gesture
            if gesture == 1 and not grasp_executado:
                rospy.loginfo("[NODE] Gesto detectado, executando grasp…")
                do_yolo_grasp(robot, grasp_cfg)
                grasp_executado = True
                gesture = 0
                rospy.sleep(2.0)
                continue

            # pega pose sim e envia
            sim = group.get_current_pose().pose
            rs = state_client.get_robot_state()
            odom_T_body = get_a_tform_b(rs.kinematic_state.transforms_snapshot,
                                        ODOM_FRAME_NAME,"body")
            flat = SE3Pose(x=sim.position.x, y=sim.position.y, z=sim.position.z,
                           rot=Quat(w=sim.orientation.w,
                                    x=sim.orientation.x,
                                    y=sim.orientation.y,
                                    z=sim.orientation.z))
            odom_T_hand = odom_T_body * flat
            cmd = RobotCommandBuilder.arm_pose_command(
                odom_T_hand.x, odom_T_hand.y, odom_T_hand.z,
                odom_T_hand.rot.w, odom_T_hand.rot.x,
                odom_T_hand.rot.y, odom_T_hand.rot.z,
                ODOM_FRAME_NAME, 0.5)
            cmd_client.robot_command(cmd)
            rate.sleep()

if __name__=="__main__":
    main()
