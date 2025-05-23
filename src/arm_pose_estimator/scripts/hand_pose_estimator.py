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

class GestureClassifierNode:
    def __init__(self):
        rospy.init_node('gesture_classifier_node')

        model_path = rospy.get_param('~model_path', '/root/ws_moveit/src/arm_pose_estimator/models/gesture_recognizer.task')
        queue_size = rospy.get_param('~queue_size', 5)
        topic_in = rospy.get_param('~input_topic', '/camera/color/image_raw')
        topic_out = rospy.get_param('~output_topic', '/hand_gesture')

        self.bridge = CvBridge()
        self.pub = rospy.Publisher(topic_out, Int32, queue_size=1)
        self.queue = deque(maxlen=queue_size)

        # Inicializa com gesto 0
        self.last_published = 0
        self.pub.publish(self.last_published)

        options = GestureRecognizerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=RunningMode.LIVE_STREAM,
            result_callback=self._on_gesture_result
        )
        self.recognizer = GestureRecognizer.create_from_options(options)

        self.sub = rospy.Subscriber(topic_in, Image, self._on_image, queue_size=1)
        rospy.loginfo('GestureClassifierNode iniciado, esperando imagens em %s', topic_in)

    def _on_image(self, msg: Image):
        try:
            bgr = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except Exception as e:
            rospy.logerr('Erro ao converter imagem: %s', e)
            return

        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

        try:
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        except Exception as e:
            rospy.logerr('Erro ao criar imagem do MediaPipe: %s', e)
            return

        timestamp_ms = msg.header.stamp.to_nsec() // 1_000_000
        self.recognizer.recognize_async(mp_image, timestamp_ms)

    def _on_gesture_result(self, result, output_image, timestamp_ms):
        if not result.gestures:
            rospy.loginfo("Nenhum gesto detectado (mão ausente ou não reconhecida)")
            return

        category = result.gestures[0][0]
        name = category.category_name.lower()
        score = category.score

        if score < 0.6:
            rospy.loginfo(f"Gesto com baixa confiança ({score:.2f}) → ignorado")
            return

        if name == 'none':
            rospy.loginfo("Gesto detectado foi 'none' → ignorado")
            return

        if name == 'closed_fist':
            val = 1
        elif name == 'open_palm':
            val = 0
        else:
            rospy.loginfo(f"Gesto '{name}' não reconhecido → ignorado")
            return

        # Filtro de suavização
        self.queue.append(val)
        mode_val = int(np.argmax(np.bincount(np.array(self.queue))))

        # Só publica se mudou
        if mode_val != self.last_published:
            rospy.loginfo(f"Gesto detectado: {name} (score: {score:.2f}) → publicado: {mode_val}")
            self.pub.publish(mode_val)
            self.last_published = mode_val

    def run(self):
        rospy.spin()

if __name__ == '__main__':
    GestureClassifierNode().run()
