#!/usr/bin/env python3

import rospy
import cv2
import cv2.aruco as aruco
import numpy as np
import tf2_ros
from geometry_msgs.msg import TransformStamped
from scipy.spatial.transform import Rotation as R
import math
from tf import transformations as tf_transformations # Para matemática de TFs

import bosdyn.client
import bosdyn.client.util
from bosdyn.client.image import ImageClient, build_image_request
from bosdyn.api import image_pb2
from bosdyn.client.lease import LeaseClient, LeaseKeepAlive, ResourceAlreadyClaimedError

# --- Configurações ---
SPOT_HOSTNAME = "192.168.80.3"
SPOT_USERNAME = "admin"
SPOT_PASSWORD = "spotadmin2017"

ARUCO_DICTIONARY = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
try:
    ARUCO_PARAMETERS = aruco.DetectorParameters_create()
except AttributeError:
    rospy.logerr("❌ Aruco 'DetectorParameters_create' não encontrado! Verifique OpenCV Contrib.")
    exit()

ARUCO_MARKER_SIZE_METERS = 0.05 # <--- 🚨 MUDE AQUI PARA O TAMANHO REAL! 🚨

IMAGE_SOURCE = "hand_color_image"
RATE_HZ = 10
WINDOW_NAME = "Spot Gripper - Aruco Debug 🔥"

TARGET_ARUCO_ID = 0
WORLD_FRAME = "map" # Frame de referência global
ROBOT_BASE_FRAME = "body" # Frame do robô que queremos localizar no map

class SpotArucoDirectLocalizer:
    def __init__(self):
        rospy.init_node('spot_aruco_direct_localizer', anonymous=True)
        rospy.loginfo("🔥 Iniciando Nó de Localização Aruco (Direto Map->Body)...")

        self.hostname = SPOT_HOSTNAME
        self.username = SPOT_USERNAME
        self.password = SPOT_PASSWORD
        self.marker_size = ARUCO_MARKER_SIZE_METERS
        self.aruco_dict = ARUCO_DICTIONARY
        self.aruco_params = ARUCO_PARAMETERS
        self.target_id = TARGET_ARUCO_ID
        self.aruco_frame_name = f"aruco_marker_{self.target_id}"

        self.sdk = None
        self.robot = None
        self.image_client = None
        self.lease_client = None
        self.lease_keepalive = None

        self.tf_buffer = tf2_ros.Buffer(rospy.Duration(10.0))
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer)
        self.tf_broadcaster = tf2_ros.TransformBroadcaster()

        self.hand_cam_frame_name = None

        rospy.loginfo(f"Localizando {ROBOT_BASE_FRAME} em {WORLD_FRAME} via Aruco {self.target_id}")
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW_NAME, 640, 480)

    def _connect_spot(self):
        # ... (código igual ao anterior) ...
        try:
            bosdyn.client.util.setup_logging(False)
            self.sdk = bosdyn.client.create_standard_sdk("ArucoDirectLocalizerClient")
            self.robot = self.sdk.create_robot(self.hostname)
            self.robot.authenticate(self.username, self.password)
            self.robot.time_sync.wait_for_sync()
            self.image_client = self.robot.ensure_client(ImageClient.default_service_name)
            self.lease_client = self.robot.ensure_client(LeaseClient.default_service_name)
            rospy.loginfo("✅ Conectado ao Spot.")
            try:
                self.lease_keepalive = LeaseKeepAlive(self.lease_client, must_acquire=True, return_at_exit=True)
                rospy.loginfo("🔑 Lease adquirido.")
                return True
            except ResourceAlreadyClaimedError:
                rospy.logerr("❌ Lease já está em uso.")
                return False
        except Exception as e:
            rospy.logerr(f"❌ Falha ao conectar ou adquirir lease: {e}")
            return False

    def _get_camera_intrinsics(self, image_response):
        # ... (código igual ao anterior) ...
        intrinsics = image_response.source.pinhole.intrinsics
        camera_matrix = np.array([
            [intrinsics.focal_length.x, 0, intrinsics.principal_point.x],
            [0, intrinsics.focal_length.y, intrinsics.principal_point.y],
            [0, 0, 1]
        ])
        distortion_coeffs = np.zeros(5)
        return camera_matrix, distortion_coeffs

    def _decode_image(self, image_response):
        # ... (código igual ao anterior) ...
        if image_response.shot.image.format == image_pb2.Image.FORMAT_RAW:
            img = np.frombuffer(image_response.shot.image.data, dtype=np.uint8)
            img = img.reshape(image_response.shot.image.rows, image_response.shot.image.cols)
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        else:
            img = cv2.imdecode(np.frombuffer(image_response.shot.image.data, dtype=np.uint8), -1)
        return img

    def _calculate_and_publish_map_to_body(self, tvec_hca, rvec_hca): # tvec/rvec da HandCam pro Aruco
        """Calcula e publica a TF map -> body."""
        try:
            rospy.logdebug("--- Iniciando Cálculo Direto Map->Body ---")

            # 1. Pega a TF do Aruco em relação ao Map (T_map_a)
            #    (Vem do launch estático: map -> zed -> aruco)
            T_map_a_msg = self.tf_buffer.lookup_transform(WORLD_FRAME, self.aruco_frame_name, rospy.Time(0), rospy.Duration(1.0))
            rospy.logdebug(f"Lookup T_map_a ({WORLD_FRAME} > {self.aruco_frame_name}): t={T_map_a_msg.transform.translation} q={T_map_a_msg.transform.rotation}")

            # 2. Pega a TF da Câmera em relação ao Body (T_body_hc)
            #    (Vem do launch estático fngr->cam + robot_state_publisher)
            T_body_hc_msg = self.tf_buffer.lookup_transform(ROBOT_BASE_FRAME, self.hand_cam_frame_name, rospy.Time(0), rospy.Duration(1.0))
            rospy.logdebug(f"Lookup T_body_hc ({ROBOT_BASE_FRAME} > {self.hand_cam_frame_name}): t={T_body_hc_msg.transform.translation} q={T_body_hc_msg.transform.rotation}")

            # --- Converte tudo para matrizes numpy ---

            # T_hc_a (HandCam -> Aruco), da detecção atual
            rot_hca_mat = R.from_rotvec(rvec_hca).as_matrix()
            T_hc_a_mat = np.identity(4)
            T_hc_a_mat[:3, :3] = rot_hca_mat
            T_hc_a_mat[:3, 3] = tvec_hca
            rospy.logdebug(f"Matriz T_hc_a (HandCam -> Aruco):\n{T_hc_a_mat}")

            # T_map_a (Map -> Aruco)
            trans_ma = [T_map_a_msg.transform.translation.x, T_map_a_msg.transform.translation.y, T_map_a_msg.transform.translation.z]
            rot_ma = [T_map_a_msg.transform.rotation.x, T_map_a_msg.transform.rotation.y, T_map_a_msg.transform.rotation.z, T_map_a_msg.transform.rotation.w]
            T_map_a_mat = tf_transformations.quaternion_matrix(rot_ma)
            T_map_a_mat[:3, 3] = trans_ma
            rospy.logdebug(f"Matriz T_map_a (Map -> Aruco):\n{T_map_a_mat}")

            # T_body_hc (Body -> HandCam)
            trans_bhc = [T_body_hc_msg.transform.translation.x, T_body_hc_msg.transform.translation.y, T_body_hc_msg.transform.translation.z]
            rot_bhc = [T_body_hc_msg.transform.rotation.x, T_body_hc_msg.transform.rotation.y, T_body_hc_msg.transform.rotation.z, T_body_hc_msg.transform.rotation.w]
            T_body_hc_mat = tf_transformations.quaternion_matrix(rot_bhc)
            T_body_hc_mat[:3, 3] = trans_bhc
            rospy.logdebug(f"Matriz T_body_hc (Body -> HandCam):\n{T_body_hc_mat}")

            # --- Cálculo das Inversas ---
            T_a_hc_mat = np.linalg.inv(T_hc_a_mat)    # Aruco -> HandCam
            T_hc_body_mat = np.linalg.inv(T_body_hc_mat) # HandCam -> Body
            rospy.logdebug("Matrizes inversas calculadas.")

            # --- Cálculo da TF map -> body ---
            # T_map_body = T_map_a * T_a_hc * T_hc_body
            T_map_body_mat = np.dot(T_map_a_mat, np.dot(T_a_hc_mat, T_hc_body_mat))
            rospy.logdebug(f"Matriz T_map_body (Map -> Body) FINAL:\n{T_map_body_mat}")

            # Extrai translação e rotação da matriz T_map_body_mat
            trans_mb = tf_transformations.translation_from_matrix(T_map_body_mat)
            rot_mb = tf_transformations.quaternion_from_matrix(T_map_body_mat)
            rospy.logdebug(f"Final trans_mb: {trans_mb}, rot_mb: {rot_mb}")

            # Publica a TF map -> body
            t = TransformStamped()
            t.header.stamp = rospy.Time.now()
            t.header.frame_id = WORLD_FRAME       # "map"
            t.child_frame_id = ROBOT_BASE_FRAME  # "body"
            t.transform.translation.x = trans_mb[0]
            t.transform.translation.y = trans_mb[1]
            t.transform.translation.z = trans_mb[2]
            t.transform.rotation.x = rot_mb[0]
            t.transform.rotation.y = rot_mb[1]
            t.transform.rotation.z = rot_mb[2]
            t.transform.rotation.w = rot_mb[3]
            self.tf_broadcaster.sendTransform(t)
            rospy.loginfo_throttle(1.0, f"📢 TF {WORLD_FRAME} -> {ROBOT_BASE_FRAME} publicada!")

        except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException) as e:
            rospy.logwarn_throttle(1.0, f"🚦 Localização Direta: Esperando TFs ({e})")
        except Exception as e:
            rospy.logerr(f"❌ Erro CABULOSO no cálculo de localização direta: {e}")

    def run(self):
        """Loop principal: Pega imagem, detecta, calcula e publica localização map->body."""
        if not self._connect_spot():
            return

        rate = rospy.Rate(RATE_HZ)

        while not rospy.is_shutdown():
            img_cv = None
            try:
                req = build_image_request(IMAGE_SOURCE, quality_percent=85)
                responses = self.image_client.get_image([req])

                if not responses:
                    rospy.logwarn_throttle(5.0, "⚠️ Nenhuma imagem recebida.")
                    rate.sleep()
                    continue

                img_resp = responses[0]
                self.hand_cam_frame_name = img_resp.shot.frame_name_image_sensor
                img_cv = self._decode_image(img_resp)
                cam_matrix, dist_coeffs = self._get_camera_intrinsics(img_resp)

                corners, ids, rejected = aruco.detectMarkers(
                    img_cv, self.aruco_dict, parameters=self.aruco_params
                )

                aruco.drawDetectedMarkers(img_cv, corners, ids, (0, 255, 0))

                if ids is not None and self.target_id in ids:
                    idx = np.where(ids == self.target_id)[0][0]
                    marker_corners = corners[idx]

                    rospy.loginfo_throttle(1.0, f"✅ Aruco ID {self.target_id} encontrado!")

                    rvecs, tvecs, _ = aruco.estimatePoseSingleMarkers(
                        [marker_corners], self.marker_size, cam_matrix, dist_coeffs
                    )
                    rvec = rvecs[0][0]
                    tvec = tvecs[0][0]

                    cv2.drawFrameAxes(img_cv, cam_matrix, dist_coeffs, rvec, tvec, self.marker_size * 0.75)
                    rospy.logdebug_throttle(1.0, f"ARUCO DETECTADO ID {self.target_id}: "
                                                f"TVEC (x,y,z): [{tvec[0]:.3f}, {tvec[1]:.3f}, {tvec[2]:.3f}] | "
                                                f"RVEC (x,y,z): [{rvec[0]:.3f}, {rvec[1]:.3f}, {rvec[2]:.3f}]")


                    # Chama a função pra calcular e publicar map -> body
                    self._calculate_and_publish_map_to_body(tvec, rvec)

                else:
                    rospy.logwarn_throttle(2.0, f"⏳ Aruco ID {self.target_id} não encontrado.")

            except Exception as e:
                rospy.logerr(f"❌ Erro no loop principal: {e}")
                rospy.sleep(1.0)

            finally:
                if img_cv is not None:
                     cv2.imshow(WINDOW_NAME, img_cv)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    rospy.signal_shutdown("Usuário pressionou 'q'.")
            rate.sleep()

    def shutdown(self):
        # ... (código igual ao anterior) ...
        rospy.loginfo("🧹 Limpando e fechando a janela...")
        cv2.destroyAllWindows()
        if self.lease_keepalive:
            self.lease_keepalive.shutdown()
        rospy.loginfo("✌️ Tamo junto!")

def main():
    localizer = SpotArucoDirectLocalizer()
    try:
        localizer.run()
    except rospy.ROSInterruptException:
        rospy.loginfo("🛑 Nó de Localização Aruco (Direto) encerrado.")
    finally:
        localizer.shutdown()

if __name__ == '__main__':
    main()