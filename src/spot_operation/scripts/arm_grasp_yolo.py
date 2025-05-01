# arm_object_grasp_yolo.py
# Copyright (c) 2023 Boston Dynamics, Inc.  All rights reserved.

import argparse
import sys
import time

import cv2
import numpy as np
import pandas as pd  # 🔥 necessário
from ultralytics import YOLO

import bosdyn.client
import bosdyn.client.estop
import bosdyn.client.util
from bosdyn.api import estop_pb2, geometry_pb2, image_pb2, manipulation_api_pb2
from bosdyn.client.estop import EstopClient
from bosdyn.client.frame_helpers import VISION_FRAME_NAME, get_vision_tform_body, math_helpers , get_a_tform_b
from bosdyn.client.image import ImageClient
from bosdyn.client.manipulation_api_client import ManipulationApiClient
from bosdyn.client.robot_command import RobotCommandClient, blocking_stand
from bosdyn.client.robot_state import RobotStateClient
from bosdyn.api import robot_command_pb2
from bosdyn.client import math_helpers
from bosdyn.client.robot_command import RobotCommandBuilder
from bosdyn.client.lease import LeaseClient, LeaseWallet, LeaseKeepAlive, add_lease_wallet_processors
from bosdyn.client.lease import ResourceAlreadyClaimedError  # Add this import

def verify_estop(robot):
    client = robot.ensure_client(EstopClient.default_service_name)
    if client.get_status().stop_level != estop_pb2.ESTOP_LEVEL_NONE:
        msg = 'Robot is estopped. Use an external E-Stop client to configure E-Stop.'
        robot.logger.error(msg)
        raise Exception(msg)

def arm_object_grasp(config):
    bosdyn.client.util.setup_logging(config.verbose)
    sdk = bosdyn.client.create_standard_sdk('ArmObjectGraspYOLO')
    robot = sdk.create_robot(config.hostname)
    robot.authenticate("admin", "spotadmin2017")
    robot.time_sync.wait_for_sync()

    cmd_client = robot.ensure_client(RobotCommandClient.default_service_name)
    robot_state_client = robot.ensure_client(RobotStateClient.default_service_name)
    image_client = robot.ensure_client(ImageClient.default_service_name)
    manipulation_api_client = robot.ensure_client(ManipulationApiClient.default_service_name)
    lease_client = robot.ensure_client(bosdyn.client.lease.LeaseClient.default_service_name)

    # Use wallet if specified
    if config.use_wallet:
        lease_wallet = LeaseWallet()
        add_lease_wallet_processors(cmd_client, lease_wallet)
        add_lease_wallet_processors(manipulation_api_client, lease_wallet)
        try:
            lease = lease_client.acquire()
        except ResourceAlreadyClaimedError:
            robot.logger.warn("Lease already claimed; forcing acquisition via take().")
            lease = lease_client.take()
        lease_wallet.add(lease)
        lease_ctx = LeaseKeepAlive(lease_client, lease_wallet,
                                  must_acquire=True, return_at_exit=False)
    else:
        lease = lease_client.take()
        lease_ctx = None

    # Execute with LeaseKeepAlive if defined
    if lease_ctx:
        lease_ctx.__enter__()

    # Load allowed objects CSV
    csv_path = "/root/ws_moveit/src/spot_operation/config/allowed_objects.csv"
    try:
        allowed_df = pd.read_csv(csv_path)
        allowed_df["class"] = allowed_df["class"].str.strip().str.lower()
        print("🧾 Objetos permitidos e prioridades:")
        print(allowed_df)
    except FileNotFoundError:
        raise RuntimeError(f"File not found: {csv_path}. Ensure the file exists and the path is correct.")

    # Load YOLO model
    print(f'🔍 Carregando modelo YOLO: {config.yolo_model}')
    yolo = YOLO(config.yolo_model)

    # Pega o estado do robô antes do grasp
    robot_state = robot_state_client.get_robot_state()
    # Extrai a transformação do corpo para a mão (end-effector)
    hand_transform = robot_state.kinematic_state.transforms_snapshot.child_to_parent_edge_map['hand'].parent_tform_child
    odom_T_body = get_a_tform_b(
        robot_state.kinematic_state.transforms_snapshot,
        "odom", "body"
    )

    # Save initial poses of the hand and base
    saved_hand_pose = math_helpers.SE3Pose.from_proto(hand_transform)
    saved_body_pose = math_helpers.SE3Pose.from_proto(odom_T_body.to_proto())

    # Captura imagem
    robot.logger.info(f'Getting image from: {config.image_source}')
    img_resp = image_client.get_image_from_sources([config.image_source])[0]
    dtype = np.uint16 if img_resp.shot.image.pixel_format == image_pb2.Image.PIXEL_FORMAT_DEPTH_U16 else np.uint8
    arr = np.frombuffer(img_resp.shot.image.data, dtype=dtype)
    if img_resp.shot.image.format == image_pb2.Image.FORMAT_RAW:
        img = arr.reshape(img_resp.shot.image.rows, img_resp.shot.image.cols)
    else:
        img = cv2.imdecode(arr, -1)

    # Detecta com YOLO
    print('🤖 Fazendo inferência com YOLO...')
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = yolo(img_rgb)
    if not results or results[0].boxes is None or len(results[0].boxes) == 0:
        raise RuntimeError('Nenhuma detecção pelo YOLO.')

    # Extrai info das detecções
    boxes = results[0].boxes.xyxy.cpu().numpy()
    classes = results[0].boxes.cls.cpu().numpy().astype(int)
    confs = results[0].boxes.conf.cpu().numpy()
    names = [results[0].names[cls].lower() for cls in classes]

    # Cria lista de detecções válidas
    filtered = []
    for i, name in enumerate(names):
        match = allowed_df[allowed_df["class"] == name]
        if not match.empty:
            priority = int(match["priority"].values[0])
            x1, y1, x2, y2 = boxes[i]
            area = (x2 - x1) * (y2 - y1)
            filtered.append((priority, -area, (x1, y1, x2, y2), name, confs[i]))

    if not filtered:
        raise RuntimeError('Nenhum objeto permitido com prioridade detectado.')

    # Ordena: menor prioridade primeiro, depois maior área
    filtered.sort()
    _, _, (x1, y1, x2, y2), name, conf = filtered[0]
    x_center = int((x1 + x2) / 2)
    y_center = int((y1 + y2) / 2)

    print(f'🎯 Objeto escolhido: "{name}" (confiança {conf:.2f}) em ({x_center}, {y_center})')

    # Monta request de pick
    pick_vec = geometry_pb2.Vec2(x=x_center, y=y_center)
    grasp = manipulation_api_pb2.PickObjectInImage(
        pixel_xy=pick_vec,
        transforms_snapshot_for_camera=img_resp.shot.transforms_snapshot,
        frame_name_image_sensor=img_resp.shot.frame_name_image_sensor,
        camera_model=img_resp.source.pinhole)

    # Aplica constraint se tiver
    add_grasp_constraint(config, grasp, robot_state_client)
    req = manipulation_api_pb2.ManipulationApiRequest(pick_object_in_image=grasp)

    # Configura timeout no planner via gRPC
    cmd_resp = manipulation_api_client.manipulation_api_command(
        manipulation_api_request=req,
        timeout=5.0)  # Timeout de 5 segundos

    # Monitor grasp feedback com timeout e retry
    start_time = time.time()
    timeout_sec = 8  # Ajusta para o tempo desejado

    while True:
        fb_req = manipulation_api_pb2.ManipulationApiFeedbackRequest(
            manipulation_cmd_id=cmd_resp.manipulation_cmd_id)
        resp = manipulation_api_client.manipulation_api_feedback_command(fb_req)
        state = manipulation_api_pb2.ManipulationFeedbackState.Name(resp.current_state)
        print(f'Current state: {state}')

        # # Se travar no WAITING_DATA_AT_EDGE além do timeout, cancela e tenta fallback
        # if (state == 'MANIP_STATE_GRASP_PLANNING_WAITING_DATA_AT_EDGE' and
        #     time.time() - start_time > timeout_sec):
        #     print('⚠️ Timeout no planejamento aguardando edge data, cancelando e tentando fallback...')
        #     manipulation_api_client.cancel_manipulation(
        #         manipulation_api_pb2.CancelManipulationRequest(
        #             manipulation_cmd_id=cmd_resp.manipulation_cmd_id))
        #     # Aqui você pode relançar outra chamada de grasp com force_top_down_grasp=True
        #     if not config.force_top_down_grasp:
        #         print("🔄 Tentando fallback com force_top_down_grasp=True...")
        #         config.force_top_down_grasp = True
        #         arm_object_grasp(config)  # Relança o grasp com o novo estilo
        #     else:
        #         print("❌ Fallback já foi tentado. Abortando.")
        #     return

        # Sai do loop se o grasp for bem-sucedido ou falhar
        if resp.current_state in (
            manipulation_api_pb2.MANIP_STATE_GRASP_SUCCEEDED,
            manipulation_api_pb2.MANIP_STATE_GRASP_FAILED):
            break
        
        time.sleep(0.25)

    if lease_ctx:
        lease_ctx.__exit__(None, None, None)

    robot.logger.info('Grasp operation completed. Robot remains powered on.')

def add_grasp_constraint(config, grasp, robot_state_client):
    use_vec = config.force_top_down_grasp or config.force_horizontal_grasp
    grasp.grasp_params.grasp_params_frame_name = VISION_FRAME_NAME
    if use_vec:
        if config.force_top_down_grasp:
            axis_g = geometry_pb2.Vec3(x=1, y=0, z=0)
            axis_v = geometry_pb2.Vec3(x=0, y=0, z=-1)
        else:
            axis_g = geometry_pb2.Vec3(x=0, y=1, z=0)
            axis_v = geometry_pb2.Vec3(x=0, y=0, z=1)
        c = grasp.grasp_params.allowable_orientation.add()
        c.vector_alignment_with_tolerance.axis_on_gripper_ewrt_gripper.CopyFrom(axis_g)
        c.vector_alignment_with_tolerance.axis_to_align_with_ewrt_frame.CopyFrom(axis_v)
        c.vector_alignment_with_tolerance.threshold_radians = 0.17
    elif config.force_45_angle_grasp:
        robot_state = robot_state_client.get_robot_state()
        vision_T_body = get_vision_tform_body(robot_state.kinematic_state.transforms_snapshot)
        body_Q = math_helpers.Quat.from_pitch(0.785398)
        vision_Q = vision_T_body.rotation * body_Q
        c = grasp.grasp_params.allowable_orientation.add()
        c.rotation_with_tolerance.rotation_ewrt_frame.CopyFrom(vision_Q.to_proto())
        c.rotation_with_tolerance.threshold_radians = 0.17
    elif config.force_squeeze_grasp:
        c = grasp.grasp_params.allowable_orientation.add()
        c.squeeze_grasp.SetInParent()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', action='store_true',
                    help='Habilita logs detalhados (debug)')
    parser.add_argument("hostname", type=str,
                        help="Hostname do Spot (ex: 192.168.80.3)")
    parser.add_argument('-i', '--image-source', default='hand_color_image',
                        help='Camera source name')
    parser.add_argument('--yolo-model', default='yolo11n.pt',
                        help='Path to YOLO model weights (e.g., yolo11n.pt)')
    parser.add_argument('--force-top-down-grasp', action='store_true',
                        help='Force a top-down grasp.')
    parser.add_argument('--force-horizontal-grasp', action='store_true',
                        help='Force a horizontal grasp.')
    parser.add_argument('--force-45-angle-grasp', action='store_true',
                        help='Force a 45 degree angle grasp.')
    parser.add_argument('--force-squeeze-grasp', action='store_true',
                        help='Force a squeeze grasp.')
    parser.add_argument('--use-wallet', action='store_true', help='Use lease wallet')
    opts = parser.parse_args()

    arm_object_grasp(opts)


if __name__ == '__main__':
    main()
