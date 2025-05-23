#!/usr/bin/env python3
import cv2
import numpy as np
import pyrealsense2 as rs
import mediapipe as mp
from collections import deque
import math
import time

# ---------- One‑Euro filter utils ----------
class OneEuroFilter:
    def __init__(self, freq, min_cutoff=1.0, beta=0.0, d_cutoff=1.0):
        self.freq = freq
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.x_prev = None
        self.dx_prev = None
        self.t_prev = None

    def _alpha(self, cutoff):
        tau = 1.0 / (2 * math.pi * cutoff)
        te = 1.0 / self.freq
        return 1.0 / (1.0 + tau / te)

    def __call__(self, x, t):
        if self.t_prev is None:
            self.x_prev, self.dx_prev, self.t_prev = x, np.zeros_like(x), t
            return x

        dt = t - self.t_prev
        if dt <= 0.0:
            return x
        self.freq = 1.0 / dt

        dx = (x - self.x_prev) * self.freq
        a_d = self._alpha(self.d_cutoff)
        dx_hat = a_d * dx + (1 - a_d) * self.dx_prev

        cutoff = self.min_cutoff + self.beta * np.abs(dx_hat)
        a = self._alpha(cutoff)
        x_hat = a * x + (1 - a) * self.x_prev

        self.x_prev, self.dx_prev, self.t_prev = x_hat, dx_hat, t
        return x_hat

# ---------- Main ----------
def main():
    # RealSense pipeline
    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
    config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
    profile = pipeline.start(config)
    align = rs.align(rs.stream.color)          # Align depth to color
    depth_scale = profile.get_device().first_depth_sensor().get_depth_scale()

    # MediaPipe Hands
    mp_hands = mp.solutions.hands
    mp_drawing = mp.solutions.drawing_utils
    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        model_complexity=1,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.8
    )

    # ---------- State holders ----------
    roi = None               # (x,y,w,h) current tracking window
    roi_expansion = 40       # pixels to grow the ROI every frame
    roi_miss_counter = 0     # how many frames we lost the hand inside ROI
    skip_tolerance = 3
    depth_prev = None
    max_depth_jump = 0.10    # meters
    filters = [OneEuroFilter(30, min_cutoff=1.5, beta=0.3) for _ in range(21)]
    time_prev = time.time()

    try:
        while True:
            frames = pipeline.wait_for_frames()
            frames = align.process(frames)
            color_frame = frames.get_color_frame()
            depth_frame = frames.get_depth_frame()
            if not color_frame or not depth_frame:
                continue

            color = np.asanyarray(color_frame.get_data())
            depth = np.asanyarray(depth_frame.get_data()) * depth_scale

            # -------------- Crop to ROI when available --------------
            if roi is not None:
                x, y, w, h = roi
                x0 = max(x - roi_expansion, 0)
                y0 = max(y - roi_expansion, 0)
                x1 = min(x + w + roi_expansion, color.shape[1])
                y1 = min(y + h + roi_expansion, color.shape[0])
                color_roi = color[y0:y1, x0:x1]
                input_img = cv2.cvtColor(color_roi, cv2.COLOR_BGR2RGB)
            else:
                input_img = cv2.cvtColor(color, cv2.COLOR_BGR2RGB)

            results = hands.process(input_img)

            hand_ok = False
            if results.multi_hand_landmarks and results.multi_hand_world_landmarks:
                hand_lms = results.multi_hand_landmarks[0]
                hand_world = results.multi_hand_world_landmarks[0].landmark

                # -------------- Depth sanity check --------------
                pts_idx = (0, 5, 17)
                depths = []
                for i in pts_idx:
                    lx = int(hand_lms.landmark[i].x * input_img.shape[1])
                    ly = int(hand_lms.landmark[i].y * input_img.shape[0])
                    if roi is not None:
                        lx += x0
                        ly += y0
                    if 0 <= lx < depth.shape[1] and 0 <= ly < depth.shape[0]:
                        depths.append(depth[ly, lx])
                if len(depths) == 3:
                    depth_cur = np.mean(depths)
                    if depth_prev is None or abs(depth_cur - depth_prev) < max_depth_jump:
                        depth_prev = depth_cur
                        hand_ok = True
                    else:
                        hand_ok = False

            # -------------- If hand passed all checks --------------
            if hand_ok:
                roi_miss_counter = 0  # reset miss counter
                # Convert landmarks to numpy arrays (world coords)
                world_pts = np.array([[lm.x, lm.y, lm.z] for lm in hand_world], dtype=np.float32)

                # Smooth with One‑Euro
                t_now = time.time()
                for i in range(21):
                    world_pts[i] = filters[i](world_pts[i], t_now)

                # Orientation (normal of triangle 0‑5‑17)
                p0, p5, p17 = world_pts[0], world_pts[5], world_pts[17]
                normal = np.cross(p17 - p0, p5 - p17)
                norm = np.linalg.norm(normal)
                normal = normal / norm if norm > 0 else np.zeros(3)
                print(f"Orientation: {normal}")

                # Draw everything
                if roi is not None:
                    # shift landmarks for drawing
                    for lm in hand_lms.landmark:
                        lm.x = (lm.x * input_img.shape[1] + x0) / color.shape[1]
                        lm.y = (lm.y * input_img.shape[0] + y0) / color.shape[0]
                mp_drawing.draw_landmarks(color, hand_lms, mp_hands.HAND_CONNECTIONS)

                # Draw orientation arrow
                h, w, _ = color.shape
                start = (int(hand_lms.landmark[0].x * w), int(hand_lms.landmark[0].y * h))
                arrow = (int(normal[0] * 100), int(-normal[1] * 100))
                end = (start[0] + arrow[0], start[1] + arrow[1])
                cv2.arrowedLine(color, start, end, (0, 255, 0), 2, tipLength=0.2)

                # Update ROI based on bounding box of landmarks
                xs = [int(lm.x * w) for lm in hand_lms.landmark]
                ys = [int(lm.y * h) for lm in hand_lms.landmark]
                x, y, w_box, h_box = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
                roi = (x, y, w_box, h_box)
            else:
                # Hand not OK this frame
                roi_miss_counter += 1
                if roi_miss_counter > skip_tolerance:
                    roi = None  # give up and use full frame
                    depth_prev = None

            # -------------- Display --------------
            cv2.imshow('Hand Orientation Robust', color)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        pipeline.stop()
        hands.close()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
