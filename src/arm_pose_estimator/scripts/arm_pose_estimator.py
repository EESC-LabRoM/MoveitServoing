#!/usr/bin/env python3
import rospy
import cv2
import cv2.aruco as aruco
import numpy as np
from cv_bridge import CvBridge
from sensor_msgs.msg import Image, CameraInfo
from message_filters import ApproximateTimeSynchronizer, Subscriber
import tf2_ros
import geometry_msgs.msg
import mediapipe as mp
import os

class ArmPoseEstimator:
    def __init__(self):
        rospy.init_node('arm_pose_estimator')
        rospy.loginfo("Initializing Arm Pose Estimator...")

        self.bridge = CvBridge()
        self.tf_broadcaster = tf2_ros.TransformBroadcaster()

        # Set DISPLAY environment variable if running headless
        if 'DISPLAY' not in os.environ:
            os.environ['DISPLAY'] = ':0'
        
        # Calibration flag and transformation from marker to camera frame
        self.calibrated = False
        self.calib_transform = None

        # Camera intrinsics (to be set from CameraInfo)
        self.camera_info_received = False
        self.camera_matrix = None
        self.dist_coeffs = None
        self.fx = None
        self.fy = None
        self.cx = None
        self.cy = None

        # Variables for temporal smoothing and jump filtering of wrist position
        self.filtered_point = None    # last valid wrist position (in marker frame)
        self.alpha = 0.5              # smoothing factor for exponential moving average
        self.change_threshold = 0.15  # maximum allowed jump (in meters) between frames

        # Check for available topics
        rospy.loginfo("Waiting for topics to be available...")
        rospy.sleep(2.0)  # Give some time for topics to be registered
        
        # Detect whether we have the double 'camera/camera' path or just 'camera'
        all_topics = rospy.get_published_topics()
        topic_names = [topic[0] for topic in all_topics]
        
        # Find the correct depth and camera info topics
        depth_topic = None
        camera_info_topic = None
        
        if '/camera/camera/aligned_depth_to_color/image_raw' in topic_names:
            depth_topic = '/camera/camera/aligned_depth_to_color/image_raw'
            camera_info_topic = '/camera/camera/aligned_depth_to_color/camera_info'
            rospy.loginfo("Using double camera path for topics")
        elif '/camera/aligned_depth_to_color/image_raw' in topic_names:
            depth_topic = '/camera/aligned_depth_to_color/image_raw'
            camera_info_topic = '/camera/aligned_depth_to_color/camera_info'
            rospy.loginfo("Using single camera path for topics")
        else:
            rospy.logerr("Could not find valid depth topic! Available topics:")
            for topic in topic_names:
                if 'depth' in topic or 'color' in topic:
                    rospy.logerr(" - " + topic)
            return

        color_topic = '/camera/color/image_raw'
        
        # Log the selected topics
        rospy.loginfo(f"Using depth topic: {depth_topic}")
        rospy.loginfo(f"Using color topic: {color_topic}")
        rospy.loginfo(f"Using camera info topic: {camera_info_topic}")

        # Subscribe to the camera info topic to get the intrinsics
        rospy.Subscriber(
            camera_info_topic,
            CameraInfo,
            self.camera_info_callback,
            queue_size=10)

        # Use message_filters to synchronize the color and depth images
        self.color_sub = Subscriber(color_topic, Image)
        self.depth_sub = Subscriber(depth_topic, Image)
        self.ats = ApproximateTimeSynchronizer([self.color_sub, self.depth_sub],
                                               queue_size=10, slop=0.1)
        self.ats.registerCallback(self.image_callback)

        # Initialize MediaPipe Pose for wrist detection
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(min_detection_confidence=0.5,
                                      min_tracking_confidence=0.5)
        rospy.loginfo("Arm Pose Estimator Initialized.")

    def camera_info_callback(self, msg):
        # Only update (and log) intrinsics once.
        if not self.camera_info_received:
            self.camera_matrix = np.array(msg.K).reshape(3, 3)
            self.dist_coeffs = np.array(msg.D)
            self.fx = self.camera_matrix[0, 0]
            self.fy = self.camera_matrix[1, 1]
            self.cx = self.camera_matrix[0, 2]
            self.cy = self.camera_matrix[1, 2]
            self.camera_info_received = True
            rospy.loginfo("Camera intrinsics received.")
            rospy.loginfo(f"Camera matrix: \n{self.camera_matrix}")
            rospy.loginfo(f"Distortion coeffs: {self.dist_coeffs}")

    def image_callback(self, color_msg, depth_msg):
        if not self.camera_info_received:
            rospy.logwarn("Waiting for camera info...")
            return

        try:
            color_image = self.bridge.imgmsg_to_cv2(color_msg, desired_encoding="bgr8")
            depth_image = self.bridge.imgmsg_to_cv2(depth_msg, desired_encoding="passthrough")
            rospy.logdebug("Successfully converted images")
        except Exception as e:
            rospy.logerr("CV Bridge error: %s" % str(e))
            return

        # Run calibration using ArUco until a marker is detected
        if not self.calibrated:
            self.calibrate(color_image)
        else:
            self.process_pose(color_image, depth_image, color_msg.header)

        # Ensure windows are created and updated
        try:
            # Update window and explicitly handle window events
            if not self.calibrated:
                pass  # Removed cv2.imshow("Calibration", color_image)
            else:
                pass  # Removed cv2.imshow("Arm Pose", color_image)
            
            # Wait for a small amount of time to process GUI events
            key = cv2.waitKey(1)
            
            # Optional: Add key handling
            if key == ord('q'):  # Quit on 'q' key
                rospy.signal_shutdown("User requested shutdown")
                
        except Exception as e:
            rospy.logerr(f"Error displaying windows: {e}")

    def calibrate(self, color_image):
        # Detect an ArUco marker to define the reference (calibration) frame.
        aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
        parameters = aruco.DetectorParameters()  # use available constructor
        corners, ids, _ = aruco.detectMarkers(color_image, aruco_dict, parameters=parameters)

        # Create a copy of the image for visualization
        display_image = color_image.copy()

        if ids is not None and len(ids) > 0:
            # Draw detected markers for visualization
            aruco.drawDetectedMarkers(display_image, corners, ids)

            # Define the marker size (in meters) – adjust as needed.
            marker_length = 0.2

            # Use the camera intrinsics obtained from CameraInfo
            rvecs, tvecs, _ = aruco.estimatePoseSingleMarkers(corners, marker_length,
                                                               self.camera_matrix,
                                                               self.dist_coeffs)
            rvec = rvecs[0][0]
            tvec = tvecs[0][0]
            
            # Draw coordinate axes on the marker
            cv2.drawFrameAxes(display_image, self.camera_matrix, self.dist_coeffs, 
                              rvec, tvec, marker_length/2)
            
            # Calculate the transform matrix
            R, _ = cv2.Rodrigues(rvec)
            transform = np.eye(4)
            transform[0:3, 0:3] = R
            transform[0:3, 3] = tvec
            self.calib_transform = transform
            self.calibrated = True
            rospy.loginfo("Calibration successful using ArUco marker.")
            rospy.loginfo(f"Marker position: {tvec}")
        else:
            # Add text to the image to guide the user
            cv2.putText(display_image, "No ArUco marker detected. Please show marker.", 
                        (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            rospy.loginfo_throttle(1.0, "Calibration: No ArUco marker detected. Please hold the marker in view.")

        # Removed cv2.imshow("Calibration", display_image)
        cv2.waitKey(1)

    def process_pose(self, color_image, depth_image, header):
        # Convert the BGR image to RGB for MediaPipe processing.
        image_rgb = cv2.cvtColor(color_image, cv2.COLOR_BGR2RGB)
        results = self.pose.process(image_rgb)

        # Create a copy of the image for visualization
        display_image = color_image.copy()

        if results.pose_landmarks:
            # Use the right wrist landmark (MediaPipe index 16) as an example.
            landmark = results.pose_landmarks.landmark[self.mp_pose.PoseLandmark.RIGHT_WRIST]

            # Check landmark visibility to filter out uncertain detections.
            if landmark.visibility < 0.6:
                cv2.putText(display_image, f"Wrist visibility low: {landmark.visibility:.2f}", 
                            (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                rospy.logwarn_throttle(1.0, "Wrist landmark visibility low (%.2f). Skipping frame." % landmark.visibility)
                return

            h, w, _ = color_image.shape
            pixel_x = int(landmark.x * w)
            pixel_y = int(landmark.y * h)

            # Get the depth value at the wrist pixel.
            if pixel_y >= depth_image.shape[0] or pixel_x >= depth_image.shape[1]:
                rospy.logwarn("Pixel coordinates out of depth image bounds!")
                return
                
            depth_mm = depth_image[pixel_y, pixel_x]
            if depth_mm == 0:
                cv2.putText(display_image, "No depth data at wrist", 
                            (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                rospy.logwarn_throttle(1.0, "Depth value at wrist is zero. Skipping this frame.")
                return
                
            depth = depth_mm / 1000.0  # Convert depth from mm to meters

            # Back-project the 2D pixel to a 3D point using the intrinsics.
            X = (pixel_x - self.cx) * depth / self.fx
            Y = (pixel_y - self.cy) * depth / self.fy
            Z = depth
            point_cam = np.array([X, Y, Z, 1]).reshape(4, 1)

            # Transform the 3D point from the camera frame to the calibration (marker) frame.
            T_inv = np.linalg.inv(self.calib_transform)
            point_marker = T_inv.dot(point_cam)
            new_point = point_marker[:3, 0]

            # Sanity check: if the new wrist position is absurdly far, skip the update.
            MAX_DISTANCE = 3.0  # adjust based on your expected scene scale (meters)
            if np.linalg.norm(new_point) > MAX_DISTANCE:
                cv2.putText(display_image, f"Wrist too far: {np.linalg.norm(new_point):.2f}m", 
                            (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                rospy.logwarn_throttle(1.0, "New wrist position is too far (%.2f m). Skipping update." % np.linalg.norm(new_point))
                return

            # Filter out sudden jumps (likely misclassifications).
            if self.filtered_point is not None:
                diff = np.linalg.norm(new_point - self.filtered_point)
                if diff > self.change_threshold:
                    cv2.putText(display_image, f"Large jump: {diff:.3f}m", 
                                (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    rospy.logwarn_throttle(1.0, "Large jump in wrist position detected (%.3f m). Ignoring update." % diff)
                    return

            # Apply exponential moving average filtering for smoothing.
            if self.filtered_point is None:
                self.filtered_point = new_point
            else:
                self.filtered_point = self.alpha * new_point + (1 - self.alpha) * self.filtered_point

            # Rebuild homogeneous coordinates for the filtered point.
            filtered_point_hom = np.array([self.filtered_point[0],
                                           self.filtered_point[1],
                                           self.filtered_point[2], 1]).reshape(4, 1)
                                           
            self.publish_tf(filtered_point_hom, header)

            # Draw a circle on the wrist in the visualization.
            cv2.circle(display_image, (pixel_x, pixel_y), 5, (0, 255, 0), -1)
            
            # Draw position text
            cv2.putText(display_image, f"X: {self.filtered_point[0]:.3f}", 
                        (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(display_image, f"Y: {self.filtered_point[1]:.3f}", 
                        (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(display_image, f"Z: {self.filtered_point[2]:.3f}", 
                        (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Draw MediaPipe pose landmarks for visualization
            self.draw_pose_landmarks(display_image, results)
            
        else:
            cv2.putText(display_image, "No pose landmarks detected", 
                        (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            rospy.loginfo_throttle(1.0, "No pose landmarks detected.")

        # Removed cv2.imshow("Arm Pose", display_image)

    def draw_pose_landmarks(self, image, results):
        """Draw the pose landmarks on the image."""
        if not results.pose_landmarks:
            return
            
        mp_drawing = mp.solutions.drawing_utils
        mp_drawing_styles = mp.solutions.drawing_styles
        
        # Draw the pose landmarks
        mp_drawing.draw_landmarks(
            image,
            results.pose_landmarks,
            self.mp_pose.POSE_CONNECTIONS,
            landmark_drawing_spec=mp_drawing_styles.get_default_pose_landmarks_style())

    def publish_tf(self, point_marker, header):
        t = geometry_msgs.msg.TransformStamped()
        t.header.stamp = header.stamp
        t.header.frame_id = "world"
        t.child_frame_id = "wrist"
        t.transform.translation.x = float(point_marker[0, 0])
        t.transform.translation.y = float(point_marker[1, 0])
        t.transform.translation.z = float(point_marker[2, 0])
        # Publish an identity quaternion since orientation is not estimated here.
        t.transform.rotation.x = 0.0
        t.transform.rotation.y = 0.0
        t.transform.rotation.z = 0.0
        t.transform.rotation.w = 1.0
        self.tf_broadcaster.sendTransform(t)
        rospy.loginfo_throttle(0.5, "Published wrist transform: [%.3f, %.3f, %.3f]" %
                      (point_marker[0, 0], point_marker[1, 0], point_marker[2, 0]))

def main():
    try:
        estimator = ArmPoseEstimator()
        rospy.spin()
    except KeyboardInterrupt:
        rospy.loginfo("Shutting down arm_pose_estimator node.")
    finally:
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()