#!/usr/bin/env python3
import rospy
import cv2
import numpy as np
import mediapipe as mp
from cv_bridge import CvBridge
from sensor_msgs.msg import Image
from geometry_msgs.msg import Quaternion
import time
import math
from tf.transformations import quaternion_from_euler
from std_msgs.msg import Int32
from collections import deque

# ---------- One‑Euro filter (igual antes, só compactei) ----------
class OneEuroFilter:
    def __init__(self, freq, min_cutoff=1.0, beta=0.0, d_cutoff=1.0):
        self.freq, self.min_cutoff, self.beta, self.d_cutoff = freq, min_cutoff, beta, d_cutoff
        self.x_prev = self.dx_prev = self.t_prev = None
    def _alpha(self, cutoff, dt):
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)
    def __call__(self, x, t):
        if self.t_prev is None:
            self.x_prev, self.dx_prev, self.t_prev = x, np.zeros_like(x), t
            return x
        dt = t - self.t_prev
        if dt <= 0.0: return x
        dx = (x - self.x_prev) / dt
        a_d = self._alpha(self.d_cutoff, dt)
        dx_hat = a_d * dx + (1 - a_d) * self.dx_prev
        cutoff = self.min_cutoff + self.beta * np.linalg.norm(dx_hat)
        a = self._alpha(cutoff, dt)
        x_hat = a * x + (1 - a) * self.x_prev
        self.x_prev, self.dx_prev, self.t_prev = x_hat, dx_hat, t
        return x_hat

def vec_to_quat(normal):
    """
    Converte o vetor normal (z) para um quaternion que alinha o frame da mão:
    - eixo z = normal
    - eixo y = -palm_direction (aprox dedo indicador)
    - eixo x = y × z
    """
    z = normal / np.linalg.norm(normal)
    y = np.array([0, -1, 0])      # fallback
    if abs(np.dot(z, y)) > 0.9:   # quase paralelo → pega outro
        y = np.array([0, 0, 1])
    x = np.cross(y, z); x /= np.linalg.norm(x)
    y = np.cross(z, x); y /= np.linalg.norm(y)
    R = np.column_stack((x, y, z))
    # Rot matriz → quat (w,x,y,z)
    qw = math.sqrt(1 + np.trace(R)) / 2.0
    qx = (R[2,1] - R[1,2]) / (4*qw)
    qy = (R[0,2] - R[2,0]) / (4*qw)
    qz = (R[1,0] - R[0,1]) / (4*qw)
    return qw, qx, qy, qz

class HandOrientationEstimator:
    def __init__(self):
        rospy.init_node('hand_orientation_rs')
        self.bridge = CvBridge()
        self.image_sub = rospy.Subscriber("/camera/color/image_raw", Image, self.image_callback)
        self.quat_pub = rospy.Publisher("/hand_roll_quat", Quaternion, queue_size=10)
        self.current_gesture = 0
        self.block_duration = 2.0        # Time to hold the quaternion (seconds)
        self.block_until = 0.0           # Timestamp until when to block
        self.last_quat_msg = None        # Stores the last quaternion
        rospy.Subscriber("/hand_gesture", Int32, self._gesture_cb)

        # MediaPipe
        mp_hands = mp.solutions.hands
        self.hands = mp_hands.Hands(
            static_image_mode=False, max_num_hands=1,
            min_detection_confidence=0.6, min_tracking_confidence=0.8)

        # Filters for 21 landmarks (adjusted parameters for smoother initialization)
        self.filters = [OneEuroFilter(freq=30, min_cutoff=0.4, beta=0.1) for _ in range(21)]

        # Buffer for delay
        self.pub_delay = rospy.Duration(0.20)     # 200 ms
        self.queue = deque()                      # [(rospy.Time, Quaternion), ...]
        # Timer to periodically publish delayed messages
        rospy.Timer(rospy.Duration(0.01), self._publish_delayed)

    def _gesture_cb(self, msg):
        prev = self.current_gesture
        self.current_gesture = msg.data
        # On transition from gesture 0 to 1, start the block timer
        if prev == 0 and self.current_gesture == 1:
            self.block_until = time.time() + self.block_duration

    def image_callback(self, msg):
        t_now = time.time()
        # If within the block period, republish the last quaternion and exit
        if self.current_gesture == 1 and t_now < self.block_until and self.last_quat_msg:
            self.quat_pub.publish(self.last_quat_msg)
            return

        if msg is None:
            return
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except Exception as e:
            rospy.logwarn(f"Erro no CvBridge: {e}")
            return

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = self.hands.process(rgb)

        if res.multi_hand_landmarks and res.multi_hand_world_landmarks:
            lm_world = res.multi_hand_world_landmarks[0].landmark
            t_now = time.time()
            world_pts = np.array([[lm.x, lm.y, lm.z] for lm in lm_world])
            for i in range(21):
                world_pts[i] = self.filters[i](world_pts[i], t_now)

            # Use 0‑5‑17 for normal calculation
            p0, p5, p17 = world_pts[0], world_pts[5], world_pts[17]
            normal = np.cross(p17 - p0, p5 - p17)
            if np.linalg.norm(normal) < 1e-6:
                return
            normal /= np.linalg.norm(normal)

            # Calculate roll angle
            roll_angle = math.atan2(normal[1], normal[0])  # atan2(Y, X)

            # Create quaternion with only roll
            qx, qy, qz, qw = quaternion_from_euler(0, 0, roll_angle)

            # Save the quaternion for reuse during the block period
            quat_msg = Quaternion()
            quat_msg.x = -qz
            quat_msg.y = qy
            quat_msg.z = qx
            quat_msg.w = qw
            self.last_quat_msg = quat_msg

            # Add to buffer with current timestamp
            self.queue.append((rospy.Time.now(), quat_msg))

    def _publish_delayed(self, event):
        """Publish all quaternions in the buffer older than pub_delay."""
        now = rospy.Time.now()
        while self.queue and (now - self.queue[0][0] >= self.pub_delay):
            _, qm = self.queue.popleft()
            self.quat_pub.publish(qm)

    def run(self):
        rospy.spin()

if __name__ == '__main__':
    estimator = HandOrientationEstimator()
    estimator.run()
