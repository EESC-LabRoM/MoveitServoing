#!/usr/bin/env python3
"""
ROS1 node that detects how many fingers (1‑4) are raised on the **right hand** (thumb ignored)
using MediaPipe Hands.  It serves a `get_finger_count` service that returns the stable count
once the same value has been seen for a configurable number of consecutive frames.

* Default camera topic: `~/input_topic` (remap or set via parameter)
* Default stability requirement: `~stable_frames` (int, default 5)
* Service type: `std_srvs/Trigger`
    * `success`  – `True` when a stable count 1‑4 is available
    * `message`  – stringified count ("1"‑"4") on success, otherwise explanation

Install dependencies:
```bash
pip install mediapipe opencv-python
sudo apt install ros-$ROS_DISTRO-cv-bridge ros-$ROS_DISTRO-image-transport
```

Launch example:
```bash
rosrun your_pkg finger_count_node.py _stable_frames:=7 _input_topic:=/camera/color/image_raw
```
Query service:
```bash
rosservice call /finger_count_node/get_finger_count
```

Replace `std_srvs/Trigger` with a custom service if you prefer an `int32` field.
"""

import rospy
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import mediapipe as mp
from collections import deque
from std_srvs.srv import Trigger, TriggerResponse


class FingerCounterNode:
    """Continuously counts raised fingers and exposes a service to retrieve a stable value."""

    def __init__(self):
        # ----- parameters -----
        self.input_topic = rospy.get_param("~input_topic", "/camera/color/image_raw")
        self.stable_frames_required = rospy.get_param("~stable_frames", 5)

        # ----- internal state -----
        self.bridge = CvBridge()
        self.current_value = 0                # last detected count (0‑4)
        self.stable_count = 0                 # how many consecutive frames show the same value
        self.last_value = None

        # ----- mediapipe setup -----
        mp_hands = mp.solutions.hands
        self.hands = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            model_complexity=0,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        # ----- ROS I/O -----
        self.sub = rospy.Subscriber(self.input_topic, Image, self.image_callback, queue_size=1)
        self.service = rospy.Service("~get_finger_count", Trigger, self.handle_service)

        rospy.loginfo("[FingerCounter] Node initialised. Waiting for images on %s", self.input_topic)

    # ------------------------------------------------------------------
    # Image callback – updates finger count every frame
    # ------------------------------------------------------------------
    def image_callback(self, msg: Image):
        try:
            frame_bgr = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            frame_bgr = cv2.flip(frame_bgr, 1)  # Flip the image horizontally
        except Exception as e:
            rospy.logwarn("[FingerCounter] cv_bridge failed: %s", e)
            return

        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        results = self.hands.process(frame_rgb)

        new_value = 0  # default when nothing detected / not right hand

        if results.multi_hand_landmarks and results.multi_handedness:
            if results.multi_handedness[0].classification[0].label == "Right":  # Use "Right" for correct hand
                lm = results.multi_hand_landmarks[0].landmark
                new_value = self._count_raised_fingers(lm)

        # ----- update stability logic -----
        if new_value == self.last_value:
            self.stable_count += 1
        else:
            self.stable_count = 1
            self.last_value = new_value
        self.current_value = new_value

    # ------------------------------------------------------------------
    # MediaPipe landmarks → count (index, middle, ring, pinky)
    # ------------------------------------------------------------------
    @staticmethod
    def _count_raised_fingers(lm):
        tips = [8, 12, 16, 20]   # fingertip landmark indices
        pips = [6, 10, 14, 18]   # proximal‑inter‑phalangeal joint indices
        count = 0
        for tip, pip in zip(tips, pips):
            if lm[tip].y < lm[pip].y:  # y is inverted: smaller means higher in image
                count += 1
        return count

    # ------------------------------------------------------------------
    # Service handler – performs active detection when called
    # ------------------------------------------------------------------
    def handle_service(self, _req):
        rospy.loginfo("[FingerCounter] Service called — starting active finger detection...")

        stable_frames = 0
        last_detected = None
        max_attempts = 50  # ~5 seconds if running at 10 Hz

        rate = rospy.Rate(10)  # 10 Hz
        attempts = 0

        while attempts < max_attempts and not rospy.is_shutdown():
            attempts += 1
            current = self.current_value

            if 1 <= current <= 4:
                if current == last_detected:
                    stable_frames += 1
                else:
                    stable_frames = 1
                    last_detected = current
            else:
                stable_frames = 0
                last_detected = None

            if stable_frames >= self.stable_frames_required:
                msg = f"{current}"
                rospy.loginfo("[FingerCounter] Stable! Returning: %s fingers", msg)
                return TriggerResponse(success=True, message=msg)

            rate.sleep()

        rospy.logwarn("[FingerCounter] Failed to detect a stable count after %d attempts.", attempts)
        return TriggerResponse(success=False, message="No stable finger count detected.")


# ----------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------

def main():
    rospy.init_node("finger_count_node", anonymous=False)
    FingerCounterNode()
    rospy.spin()


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass
