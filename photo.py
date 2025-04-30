#!/usr/bin/env python3
import os
import sys
import time
import json
import numpy as np
import cv2

# 1. Ensure YOLOv11 weights are available locally
weights_dir  = 'weights'
weights_file = 'yolo11n.pt'
weights_path = os.path.join(weights_dir, weights_file)
if not os.path.isfile(weights_path):
    print(f"ERROR: Missing weights at '{weights_path}'.", file=sys.stderr)
    sys.exit(1)

from ultralytics import YOLO
from bosdyn.client import create_standard_sdk, util
from bosdyn.client.image import ImageClient, build_image_request
from bosdyn.client.robot_state import RobotStateClient
from bosdyn.client.lease import LeaseClient, LeaseKeepAlive, ResourceAlreadyClaimedError
from bosdyn.client.robot_command import (
    RobotCommandClient,
    RobotCommandBuilder,
    block_until_arm_arrives,
)
from bosdyn.client.frame_helpers import get_a_tform_b, VISION_FRAME_NAME, HAND_FRAME_NAME
from bosdyn.client.math_helpers import SE3Pose, Vec3

# 2. SDK & Clients Setup
sdk   = create_standard_sdk('bottle_reconstruct')
robot = sdk.create_robot('192.168.80.3')
util.authenticate(robot)
robot.time_sync.wait_for_sync()

img_client   = robot.ensure_client(ImageClient.default_service_name)
state_client = robot.ensure_client(RobotStateClient.default_service_name)
lease_client = robot.ensure_client(LeaseClient.default_service_name)
cmd_client   = robot.ensure_client(RobotCommandClient.default_service_name)

# 3. Acquire Lease & Open Gripper
try:
    lease_wrapper = lease_client.acquire()
except ResourceAlreadyClaimedError:
    lease_wrapper = lease_client.take()
keep_alive = LeaseKeepAlive(lease_client)
lease = lease_wrapper.lease_proto

open_cmd = RobotCommandBuilder.claw_gripper_open_fraction_command(1.0)
cmd_client.robot_command(open_cmd, lease=lease)
time.sleep(1.5)

# 4. Initial RGB + Depth Capture
requests = [
    build_image_request('frontleft_fisheye_image', quality_percent=90),
    build_image_request('frontleft_depth')
]
resp_color, resp_depth = img_client.get_image(requests)

img = cv2.imdecode(
    np.frombuffer(resp_color.shot.image.data, np.uint8),
    cv2.IMREAD_COLOR
)
os.makedirs('captures', exist_ok=True)
cv2.imwrite('captures/initial_view.jpg', img)

depth_raw = np.frombuffer(resp_depth.shot.image.data, dtype=np.uint16)
depth_raw = depth_raw.reshape(resp_depth.shot.image.rows, resp_depth.shot.image.cols)
depth_map = depth_raw * resp_depth.source.depth_scale

# 5. YOLOv11 Detection & Annotation
model   = YOLO(weights_path)
results = model.predict(source=img, max_det=1000)

annot     = results[0].plot()
annot_bgr = cv2.cvtColor(annot, cv2.COLOR_RGB2BGR)
cv2.imwrite('captures/initial_view_preds.jpg', annot_bgr)

boxes   = results[0].boxes.xyxy.cpu().numpy()
confs   = results[0].boxes.conf.cpu().numpy()
cls_ids = results[0].boxes.cls.cpu().numpy().astype(int)
idxs    = np.where((cls_ids == 56) & (confs > 0.2))[0]
if idxs.size == 0:
    print("No bottle detected.", file=sys.stderr)
    sys.exit(1)
x1, y1, x2, y2 = boxes[idxs[0]]
u_rgb, v_rgb   = int((x1 + x2) / 2), int((y1 + y2) / 2)

# 6. Map to Depth & Back-Project to Camera Frame
h_img, w_img     = img.shape[:2]
h_depth, w_depth = depth_map.shape
u_d = min(max(int(u_rgb * w_depth / w_img), 0), w_depth - 1)
v_d = min(max(int(v_rgb * h_depth / h_img), 0), h_depth - 1)
Z   = float(depth_map[v_d, u_d])

fx, fy, cx, cy = 600.0, 600.0, 320.0, 240.0
X = (u_rgb - cx) * Z / fx
Y = (v_rgb - cy) * Z / fy

# 7. Compute World-Frame Bottle Center & Initial Orientation
frame_tree = robot.get_frame_tree_snapshot()
T_vis_hand = get_a_tform_b(frame_tree, VISION_FRAME_NAME, HAND_FRAME_NAME)
pose_proto0 = T_vis_hand.to_proto()
pose_world0 = SE3Pose.from_proto(pose_proto0)
rot0        = pose_world0.rot
p_world_vec = pose_world0.transform_vec3(Vec3(X, Y, Z))
p_world     = [p_world_vec.x, p_world_vec.y, p_world_vec.z]

# 8. Corrected Spherical Sweep
radius = 0.5
yaws   = np.linspace(0, 360, 8, endpoint=False)
pits   = [-20, 0, 20]
captures = []

for yaw in yaws:
    for pit in pits:
        dx = radius * np.cos(np.deg2rad(pit)) * np.cos(np.deg2rad(yaw))
        dy = radius * np.cos(np.deg2rad(pit)) * np.sin(np.deg2rad(yaw))
        dz = radius * np.sin(np.deg2rad(pit))
        target = [
            p_world[0] + dx,
            p_world[1] + dy,
            p_world[2] + dz
        ]

        new_pose = SE3Pose(
            target[0], target[1], target[2],
            rot0
        )  # __init__(x, y, z, rot) 
        pose_proto = new_pose.to_proto()

        arm_cmd = RobotCommandBuilder.arm_pose_command_from_pose(
            hand_pose=pose_proto,
            frame_name=VISION_FRAME_NAME,
            seconds=5.0
        )  # 
        cmd_id = cmd_client.robot_command(arm_cmd, lease=lease)
        block_until_arm_arrives(cmd_client, cmd_id, timeout_sec=10.0)  # 

        resp = img_client.get_image([
            build_image_request('frontleft_fisheye_image', quality_percent=90)
        ])[0]
        frame = cv2.imdecode(
            np.frombuffer(resp.shot.image.data, np.uint8),
            cv2.IMREAD_COLOR
        )
        fname = f'captures/img_{len(captures):03d}.jpg'
        cv2.imwrite(fname, frame)
        captures.append({'file': fname, 'yaw': float(yaw), 'pit': float(pit)})

# 9. Save Metadata & Clean Up
with open('captures/metadata.json', 'w') as f:
    json.dump(captures, f, indent=2)

lease_client.return_lease(lease_wrapper)
keep_alive.shutdown()

print(f"Captured {len(captures)} images around the bottle.")
