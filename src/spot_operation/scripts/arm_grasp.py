# Copyright (c) 2023 Boston Dynamics, Inc.  All rights reserved.
#
# Downloading, reproducing, distributing or otherwise using the SDK Software
# is subject to the terms and conditions of the Boston Dynamics Software
# Development Kit License (20191101-BDSDK-SL).

"""Tutorial to show how to use Spot's arm, assuming the robot is already powered on and standing."""
import argparse
import sys
import time

import cv2
import numpy as np

import bosdyn.client
import bosdyn.client.estop
import bosdyn.client.lease
import bosdyn.client.util
from bosdyn.api import estop_pb2, geometry_pb2, image_pb2, manipulation_api_pb2
from bosdyn.client.estop import EstopClient
from bosdyn.client.frame_helpers import VISION_FRAME_NAME, get_vision_tform_body, math_helpers
from bosdyn.client.image import ImageClient
from bosdyn.client.manipulation_api_client import ManipulationApiClient
from bosdyn.client.robot_command import RobotCommandClient
from bosdyn.client.robot_state import RobotStateClient

# Global variables for image click

g_image_click = None
g_image_display = None


def verify_estop(robot):
    """Verify the robot is not estopped"""
    client = robot.ensure_client(EstopClient.default_service_name)
    if client.get_status().stop_level != estop_pb2.ESTOP_LEVEL_NONE:
        error_message = 'Robot is estopped. Please use an external E-Stop client.'
        robot.logger.error(error_message)
        raise Exception(error_message)


def arm_object_grasp(config):
    """Example of using the Boston Dynamics API to command Spot's arm."""

    bosdyn.client.util.setup_logging(config.verbose)
    sdk = bosdyn.client.create_standard_sdk('ArmObjectGraspClient')
    robot = sdk.create_robot(config.hostname)
    bosdyn.client.util.authenticate(robot)
    robot.time_sync.wait_for_sync()

    assert robot.has_arm(), 'Robot requires an arm to run this example.'
    verify_estop(robot)

    lease_client = robot.ensure_client(bosdyn.client.lease.LeaseClient.default_service_name)
    robot_state_client = robot.ensure_client(RobotStateClient.default_service_name)
    image_client = robot.ensure_client(ImageClient.default_service_name)
    manipulation_api_client = robot.ensure_client(ManipulationApiClient.default_service_name)

    # Forcefully take the lease if already claimed
    lease = lease_client.take()
    with bosdyn.client.lease.LeaseKeepAlive(lease_client, must_acquire=False, return_at_exit=True):
        # Robot is assumed powered on and standing

        # Capture an image
        robot.logger.info('Getting an image from: %s', config.image_source)
        image_responses = image_client.get_image_from_sources([config.image_source])
        if len(image_responses) != 1:
            raise RuntimeError(f'Invalid number of images: {len(image_responses)}')

        image = image_responses[0]
        dtype = np.uint16 if image.shot.image.pixel_format == image_pb2.Image.PIXEL_FORMAT_DEPTH_U16 else np.uint8
        arr = np.frombuffer(image.shot.image.data, dtype=dtype)
        if image.shot.image.format == image_pb2.Image.FORMAT_RAW:
            img = arr.reshape(image.shot.image.rows, image.shot.image.cols)
        else:
            img = cv2.imdecode(arr, -1)

        # Show and click to grasp
        robot.logger.info('Click on an object to start grasping...')
        title = 'Click to grasp'
        cv2.namedWindow(title)
        cv2.setMouseCallback(title, cv_mouse_callback)
        global g_image_click, g_image_display
        g_image_display = img.copy()
        cv2.imshow(title, g_image_display)
        while g_image_click is None:
            if cv2.waitKey(1) & 0xFF in (ord('q'), ord('Q')):
                sys.exit(0)

        robot.logger.info(f'Picking object at image location {g_image_click}')
        pick_vec = geometry_pb2.Vec2(x=g_image_click[0], y=g_image_click[1])
        grasp = manipulation_api_pb2.PickObjectInImage(
            pixel_xy=pick_vec,
            transforms_snapshot_for_camera=image.shot.transforms_snapshot,
            frame_name_image_sensor=image.shot.frame_name_image_sensor,
            camera_model=image.source.pinhole)

        add_grasp_constraint(config, grasp, robot_state_client)
        req = manipulation_api_pb2.ManipulationApiRequest(pick_object_in_image=grasp)
        cmd_resp = manipulation_api_client.manipulation_api_command(
            manipulation_api_request=req)

        # Feedback loop
        while True:
            fb_req = manipulation_api_pb2.ManipulationApiFeedbackRequest(
                manipulation_cmd_id=cmd_resp.manipulation_cmd_id)
            resp = manipulation_api_client.manipulation_api_feedback_command(
                manipulation_api_feedback_request=fb_req)
            state = manipulation_api_pb2.ManipulationFeedbackState.Name(resp.current_state)
            print(f'Current state: {state}')
            if resp.current_state in (
                manipulation_api_pb2.MANIP_STATE_GRASP_SUCCEEDED,
                manipulation_api_pb2.MANIP_STATE_GRASP_FAILED):
                break
            time.sleep(0.25)

        robot.logger.info('Finished grasp.')


def cv_mouse_callback(event, x, y, flags, param):
    global g_image_click, g_image_display
    clone = g_image_display.copy()
    if event == cv2.EVENT_LBUTTONUP:
        g_image_click = (x, y)
    else:
        h, w = clone.shape[:2]
        cv2.line(clone, (0, y), (w, y), (30, 30, 30), 2)
        cv2.line(clone, (x, 0), (x, h), (30, 30, 30), 2)
        cv2.imshow('Click to grasp', clone)


def add_grasp_constraint(config, grasp, robot_state_client):
    use_vector = config.force_top_down_grasp or config.force_horizontal_grasp
    grasp.grasp_params.grasp_params_frame_name = VISION_FRAME_NAME
    if use_vector:
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
    bosdyn.client.util.add_base_arguments(parser)
    parser.add_argument('-i', '--image-source', default='frontleft_fisheye_image')
    parser.add_argument('-t', '--force-top-down-grasp', action='store_true')
    parser.add_argument('-f', '--force-horizontal-grasp', action='store_true')
    parser.add_argument('-r', '--force-45-angle-grasp', action='store_true')
    parser.add_argument('-s', '--force-squeeze-grasp', action='store_true')
    opts = parser.parse_args()

    if sum([opts.force_top_down_grasp, opts.force_horizontal_grasp, opts.force_45_angle_grasp, opts.force_squeeze_grasp]) > 1:
        print('Error: choose only one grasp constraint.')
        sys.exit(1)

    try:
        arm_object_grasp(opts)
        return True
    except Exception as e:
        logger = bosdyn.client.util.get_logger()
        logger.exception('Exception in arm_object_grasp')
        return False

if __name__ == '__main__':
    if not main():
        sys.exit(1)