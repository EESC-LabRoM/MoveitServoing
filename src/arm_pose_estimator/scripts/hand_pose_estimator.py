#!/usr/bin/env python3
import rospy
from sensor_msgs.msg import Image
from std_msgs.msg import Int32
from cv_bridge import CvBridge
import cv2
import numpy as np
from collections import deque
import mediapipe as mp
from mediapipe.tasks.python.core.base_options import BaseOptions
from mediapipe.tasks.python.vision import GestureRecognizer, GestureRecognizerOptions, RunningMode
from mediapipe.tasks.python.vision import GestureRecognizerResult

class GestureClassifierNode:
    def __init__(self):
        rospy.init_node('gesture_classifier_node')

        # ROS parameters
        model_path = rospy.get_param('~model_path', '/root/ws_moveit/src/arm_pose_estimator/models/gesture_recognizer.task')
        queue_size = rospy.get_param('~queue_size', 5)
        topic_in = rospy.get_param('~input_topic', '/camera/color/image_raw')
        topic_out = rospy.get_param('~output_topic', '/hand_gesture')

        # Setup
        self.bridge = CvBridge()
        self.pub = rospy.Publisher(topic_out, Int32, queue_size=1)
        self.queue = deque(maxlen=queue_size)

        # Initialize gesture to 0
        self.pub.publish(0)

        # Configure MediaPipe GestureRecognizer for live stream
        options = GestureRecognizerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=RunningMode.LIVE_STREAM,
            result_callback=self._on_gesture_result
        )
        self.recognizer = GestureRecognizer.create_from_options(options)

        # Subscribe to image topic
        self.sub = rospy.Subscriber(topic_in, Image, self._on_image, queue_size=1)
        rospy.loginfo('GestureClassifierNode iniciado, esperando imagens em %s', topic_in)

    def _on_image(self, msg: Image):
        #rospy.loginfo_throttle(5, "Frame recebido em %s", msg.header.stamp)  # a cada 5 s
        # Convert ROS Image to RGB numpy
        try:
            bgr = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except Exception as e:
            rospy.logerr('CvBridge error: %s', e)
            return
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

        # Create MediaPipe Image
        try:
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        except Exception as e:
            rospy.logerr('Error creating MediaPipe Image: %s', e)
            return

        timestamp_ms = msg.header.stamp.to_nsec() // 1_000_000
        self.recognizer.recognize_async(mp_image, timestamp_ms)

    def _on_gesture_result(self, result, output_image, timestamp_ms):
        if not result.gestures:
            self.pub.publish(0)  # Reset gesture to 0 if no gestures are detected
            return

        category = result.gestures[0][0]

        # Só considera se o score for minimamente confiável
        if category.score < 0.6:
            self.pub.publish(0)  # Reset gesture to 0 if confidence is too low
            return

        # Valida o nome do gesto (tudo lowercase pra segurança)
        name = category.category_name.lower()
        if name == 'closed_fist':
            val = 1
        elif name == 'open_palm':
            val = 0
        else:
            self.pub.publish(0)  # Reset gesture to 0 for unrecognized gestures
            return

        # Filtro de suavização
        self.queue.append(val)
        mode_val = int(np.argmax(np.bincount(np.array(self.queue))))

        self.pub.publish(mode_val)
        rospy.loginfo('Published gesture: %d', mode_val)

    def run(self):
        rospy.spin()

if __name__ == '__main__':
    GestureClassifierNode().run()
