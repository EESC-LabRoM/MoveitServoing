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
import threading  # Para proteger acesso à última TF publicada

# --- Configurações ---
SPOT_HOSTNAME = "192.168.80.3"
SPOT_USERNAME = "admin"
SPOT_PASSWORD = "spotadmin2017"

ARUCO_DICTIONARY_NAME = aruco.DICT_4X4_50
try:
    ARUCO_PARAMETERS = aruco.DetectorParameters_create()
except AttributeError:
    try:
        ARUCO_PARAMETERS = aruco.DetectorParameters()
        rospy.logwarn("Usando aruco.DetectorParameters()")
    except AttributeError:
        rospy.logerr("❌ Aruco 'DetectorParameters' ou '_create' não encontrado!")
        rospy.signal_shutdown("OpenCV Contrib não encontrado")
        # exit() # Comentado para permitir que o script continue se o import falhar, mas a detecção não funcionará

ARUCO_MARKER_SIZE_METERS = 0.2 # 🚨 SEU TAMANHO DE ARUCO AQUI (0.2m = 20cm) 🚨
# Garanta que este tamanho é o MESMO usado no script da ZED!

IMAGE_SOURCE_SPOT = "hand_color_image" # Imagem da garra do Spot
RATE_HZ = 10
WINDOW_NAME_SPOT = "Spot Aruco Localization Debug 🔥"

TARGET_ARUCO_ID = 0 # O MESMO ID que a ZED está procurando
WORLD_FRAME = "map"
ODOM_FRAME = "odom" # Frame que vamos conectar ao map
ROBOT_BASE_FRAME = "body" # Frame base do Spot

class SpotArucoLocalizer:
    def __init__(self):
        rospy.init_node('spot_aruco_localizer', anonymous=True)
        rospy.loginfo("🔥 Iniciando Nó de Localização Aruco do SPOT...")

        self.hostname = SPOT_HOSTNAME
        self.username = SPOT_USERNAME
        self.password = SPOT_PASSWORD
        self.marker_size = ARUCO_MARKER_SIZE_METERS
        self.aruco_dict = aruco.getPredefinedDictionary(ARUCO_DICTIONARY_NAME)
        self.aruco_params = ARUCO_PARAMETERS # Já tratado com try-except acima
        self.target_id = TARGET_ARUCO_ID
        self.aruco_frame_name = f"aruco_marker_{self.target_id}" # Este é o Aruco publicado pela ZED

        self.sdk = None
        self.robot = None
        self.image_client_spot = None # Renomeado para clareza
        self.lease_client = None
        self.lease_keepalive = None

        self.tf_buffer = tf2_ros.Buffer(rospy.Duration(10.0)) 
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer)
        self.tf_broadcaster = tf2_ros.TransformBroadcaster()

        self.hand_cam_frame_name_spot = None # Frame da câmera do Spot

        self.last_published_map_to_target_tf = None  # Armazena a última TF (map->odom ou map->body)
        self.tf_update_lock = threading.Lock()  # Protege o acesso à última TF
        self.max_translation_jump = 0.5  # Máximo salto permitido em metros (ex: 50cm)
        self.max_rotation_jump_rad = math.radians(30)  # Máximo salto rotacional permitido (30 graus)

        self.last_published_map_to_body_tf_msg = None  # Última TransformStamped publicada
        self.tf_filter_lock = threading.Lock()  # Protege o acesso
        self.max_translation_jump = 0.2  # Máximo salto permitido (20cm)
        self.max_rotation_jump_rad = math.radians(15)  # Máximo salto rotacional permitido (15 graus)

        self.translation_buffer = []  # Buffer para média móvel de translação
        self.rotation_buffer_quat = []  # Buffer para quatérnios
        self.smoothing_buffer_size = 5  # Tamanho do buffer para suavização

        self.tf_publish_timer = rospy.Timer(rospy.Duration(1.0 / RATE_HZ), self.publish_smoothed_tf_callback)

        rospy.loginfo(f"Tentando localizar {ODOM_FRAME} em {WORLD_FRAME} usando Aruco ID {self.target_id}")
        # cv2.namedWindow(WINDOW_NAME_SPOT, cv2.WINDOW_NORMAL) # Debug visual opcional
        # cv2.resizeWindow(WINDOW_NAME_SPOT, 640, 480)

    def _connect_spot(self):
        try:
            bosdyn.client.util.setup_logging(False)
            self.sdk = bosdyn.client.create_standard_sdk("SpotArucoLocalizerClient")
            self.robot = self.sdk.create_robot(self.hostname)
            self.robot.authenticate(self.username, self.password)
            self.robot.time_sync.wait_for_sync()
            self.image_client_spot = self.robot.ensure_client(ImageClient.default_service_name)
            self.lease_client = self.robot.ensure_client(LeaseClient.default_service_name)
            rospy.loginfo("SPOT Localizer: ✅ Conectado ao Spot.")
            try:
                self.lease_keepalive = LeaseKeepAlive(self.lease_client, must_acquire=True, return_at_exit=True)
                rospy.loginfo("SPOT Localizer: 🔑 Lease adquirido.")
                return True
            except ResourceAlreadyClaimedError:
                rospy.logerr("SPOT Localizer: ❌ Lease já está em uso.")
                return False
        except Exception as e:
            rospy.logerr(f"SPOT Localizer: ❌ Falha ao conectar ou adquirir lease: {e}")
            return False

    def _get_camera_intrinsics_spot(self, image_response):
        rospy.logdebug("SPOT Localizer DBG: Entrando em _get_camera_intrinsics_spot")
        intrinsics = image_response.source.pinhole.intrinsics
        camera_matrix = np.array([
            [intrinsics.focal_length.x, 0, intrinsics.principal_point.x],
            [0, intrinsics.focal_length.y, intrinsics.principal_point.y],
            [0, 0, 1]
        ])
        rospy.logdebug(f"SPOT Localizer DBG: Matriz da câmera Spot: {camera_matrix.flatten().tolist()}")

        distortion_coeffs = np.zeros(5)  # Default to zeros as a safe fallback

        try:
            if image_response.source.pinhole.HasField('distortion') and \
               image_response.source.pinhole.distortion.params:
                
                coeffs_from_sdk = list(image_response.source.pinhole.distortion.params)
                rospy.loginfo_throttle(5.0, f"SPOT Localizer: SDK forneceu {len(coeffs_from_sdk)} coef. de distorção: {coeffs_from_sdk}")

                num_coeffs_to_use = min(len(coeffs_from_sdk), 5)
                for i in range(num_coeffs_to_use):
                    distortion_coeffs[i] = coeffs_from_sdk[i]
                
                if len(coeffs_from_sdk) < 5 and len(coeffs_from_sdk) > 0:
                    rospy.logwarn_throttle(5.0, f"SPOT Localizer: SDK forneceu menos de 5 coef. de distorção. Usando os {len(coeffs_from_sdk)} primeiros e zerando o resto.")
                elif not coeffs_from_sdk:
                    rospy.logwarn_throttle(5.0, "SPOT Localizer: SDK forneceu lista de params de distorção VAZIA. Usando todos zeros.")

            else:
                rospy.logwarn_throttle(5.0, "SPOT Localizer: Campo 'distortion' ou 'distortion.params' não encontrado ou vazio na ImageResponse. Usando coeficientes de distorção como zeros.")
        
        except AttributeError as ae:
            rospy.logwarn_throttle(5.0, f"SPOT Localizer: AttributeError ao acessar distortion.params (Campo pode não existir): {ae}. Usando zeros.")
        except Exception as e:
            rospy.logwarn_throttle(5.0, f"SPOT Localizer: Erro inesperado ao processar distortion.params: {e}. Usando zeros.")
        
        rospy.loginfo_throttle(5.0, f"SPOT Localizer: Coeficientes de Distorção Usados para Spot Hand Camera: {distortion_coeffs.flatten().tolist()}")
        return camera_matrix, distortion_coeffs

    def _decode_image_spot(self, image_response): # Renomeado para clareza
        if image_response.shot.image.format == image_pb2.Image.FORMAT_RAW:
            img = np.frombuffer(image_response.shot.image.data, dtype=np.uint8)
            img = img.reshape(image_response.shot.image.rows, image_response.shot.image.cols)
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        else:
            img = cv2.imdecode(np.frombuffer(image_response.shot.image.data, dtype=np.uint8), -1)
        return img

    def publish_smoothed_tf_callback(self, event):
        with self.tf_filter_lock:
            if self.last_published_map_to_body_tf_msg:
                self.last_published_map_to_body_tf_msg.header.stamp = rospy.Time.now()
                self.tf_broadcaster.sendTransform(self.last_published_map_to_body_tf_msg)
                rospy.logdebug_throttle(1.0, f"SMOOTH TF: {self.last_published_map_to_body_tf_msg.header.frame_id} -> {self.last_published_map_to_body_tf_msg.child_frame_id} publicada")
            else:
                rospy.logdebug_throttle(5.0, "SMOOTH TF: Nenhuma TF suavizada para publicar ainda.")

    def _calculate_and_publish_map_to_body(self, tvec_hca, rvec_hca): # tvec/rvec da HandCam pro Aruco
        """Calcula e publica a TF map -> body DIRETAMENTE."""
        try:
            rospy.loginfo_throttle(1.0, "--- SPOT Localizer (Direto): Iniciando Cálculo Map->Body ---")

            # 1. Pega T_map_a (Map -> Aruco) - Publicada pelo nó da ZED
            T_map_a_msg = self.tf_buffer.lookup_transform(WORLD_FRAME, self.aruco_frame_name, rospy.Time(0), rospy.Duration(1.0))
            rospy.loginfo_throttle(1.0, f"SPOT Localizer (Direto) DBG: T_map_a ({WORLD_FRAME} > {self.aruco_frame_name}): tZ={T_map_a_msg.transform.translation.z:.3f}")

            # 2. Pega T_body_hc (Body -> HandCam do Spot) - Vem do launch estático fngr->cam + robot_state_publisher
            T_body_hc_msg = self.tf_buffer.lookup_transform(ROBOT_BASE_FRAME, self.hand_cam_frame_name_spot, rospy.Time(0), rospy.Duration(1.0))
            rospy.loginfo_throttle(1.0, f"SPOT Localizer (Direto) DBG: T_body_hc ({ROBOT_BASE_FRAME} > {self.hand_cam_frame_name_spot}): tX={T_body_hc_msg.transform.translation.x:.3f}")

            # --- Converte tudo para matrizes numpy ---
            # T_hc_a (HandCam -> Aruco), da detecção atual do SPOT
            rot_hca_mat = R.from_rotvec(rvec_hca.flatten()).as_matrix()
            T_hc_a_mat = np.identity(4)
            T_hc_a_mat[:3, :3] = rot_hca_mat
            T_hc_a_mat[:3, 3] = tvec_hca.flatten()

            # T_map_a (Map -> Aruco)
            trans_ma = [T_map_a_msg.transform.translation.x, T_map_a_msg.transform.translation.y, T_map_a_msg.transform.translation.z]
            rot_ma = [T_map_a_msg.transform.rotation.x, T_map_a_msg.transform.rotation.y, T_map_a_msg.transform.rotation.z, T_map_a_msg.transform.rotation.w]
            T_map_a_mat = tf_transformations.quaternion_matrix(rot_ma)
            T_map_a_mat[:3, 3] = trans_ma

            # T_body_hc (Body -> HandCam)
            trans_bhc = [T_body_hc_msg.transform.translation.x, T_body_hc_msg.transform.translation.y, T_body_hc_msg.transform.translation.z]
            rot_bhc = [T_body_hc_msg.transform.rotation.x, T_body_hc_msg.transform.rotation.y, T_body_hc_msg.transform.rotation.z, T_body_hc_msg.transform.rotation.w]
            T_body_hc_mat = tf_transformations.quaternion_matrix(rot_bhc)
            T_body_hc_mat[:3, 3] = trans_bhc

            # --- Cálculo das Inversas ---
            T_a_hc_mat = np.linalg.inv(T_hc_a_mat)        # Aruco -> HandCam_Spot
            T_hc_body_mat = np.linalg.inv(T_body_hc_mat) # HandCam_Spot -> Body

            # --- Cálculo da TF map -> body ---
            # T_map_body = T_map_a * T_a_hc * T_hc_body
            T_map_body_mat = np.dot(T_map_a_mat, np.dot(T_a_hc_mat, T_hc_body_mat))
            current_trans_mb = tf_transformations.translation_from_matrix(T_map_body_mat)
            current_rot_mb_quat = tf_transformations.quaternion_from_matrix(T_map_body_mat)

            with self.tf_filter_lock:
                publish_this_tf = True
                if self.last_published_map_to_body_tf_msg:
                    last_trans = np.array([
                        self.last_published_map_to_body_tf_msg.transform.translation.x,
                        self.last_published_map_to_body_tf_msg.transform.translation.y,
                        self.last_published_map_to_body_tf_msg.transform.translation.z
                    ])
                    translation_diff = np.linalg.norm(current_trans_mb - last_trans)
                    if translation_diff > self.max_translation_jump:
                        rospy.logwarn_throttle(1.0, f"SPOT Localizer: SALTO GRANDE na translação: {translation_diff:.3f}m. Ignorando.")
                        publish_this_tf = False

                    q_last = np.array([
                        self.last_published_map_to_body_tf_msg.transform.rotation.x,
                        self.last_published_map_to_body_tf_msg.transform.rotation.y,
                        self.last_published_map_to_body_tf_msg.transform.rotation.z,
                        self.last_published_map_to_body_tf_msg.transform.rotation.w
                    ])
                    dot_product = np.abs(np.dot(q_last, current_rot_mb_quat))
                    if dot_product < 1.0:
                        angle_diff_rad = 2 * math.acos(dot_product)
                        if angle_diff_rad > self.max_rotation_jump_rad:
                            rospy.logwarn_throttle(1.0, f"SPOT Localizer: SALTO GRANDE na rotação: {math.degrees(angle_diff_rad):.1f} graus. Ignorando.")
                            publish_this_tf = False

                if publish_this_tf:
                    self.translation_buffer.append(current_trans_mb)
                    self.rotation_buffer_quat.append(current_rot_mb_quat)
                    if len(self.translation_buffer) > self.smoothing_buffer_size:
                        self.translation_buffer.pop(0)
                        self.rotation_buffer_quat.pop(0)

                    smoothed_trans = np.mean(self.translation_buffer, axis=0)
                    smoothed_rot_quat = self.rotation_buffer_quat[-1] if self.rotation_buffer_quat else current_rot_mb_quat

                    t_smooth = TransformStamped()
                    t_smooth.header.stamp = rospy.Time.now()
                    t_smooth.header.frame_id = WORLD_FRAME
                    t_smooth.child_frame_id = ROBOT_BASE_FRAME
                    t_smooth.transform.translation.x = smoothed_trans[0]
                    t_smooth.transform.translation.y = smoothed_trans[1]
                    t_smooth.transform.translation.z = smoothed_trans[2]
                    t_smooth.transform.rotation.x = smoothed_rot_quat[0]
                    t_smooth.transform.rotation.y = smoothed_rot_quat[1]
                    t_smooth.transform.rotation.z = smoothed_rot_quat[2]
                    t_smooth.transform.rotation.w = smoothed_rot_quat[3]

                    self.last_published_map_to_body_tf_msg = t_smooth
                    rospy.loginfo_throttle(1.0, f"📢 SPOT Localizer: TF Suavizada (map -> {ROBOT_BASE_FRAME}) ATUALIZADA! Z: {smoothed_trans[2]:.3f}")

        except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException) as e:
            rospy.logwarn_throttle(1.0, f"🚦 SPOT Localizer: Esperando por TFs para cálculo ({e})")
        except Exception as e:
            rospy.logerr(f"❌ SPOT Localizer: Erro no cálculo de localização: {e}")

    def run(self):
        if not self._connect_spot():
            return

        rate = rospy.Rate(RATE_HZ)
        debug_img_spot = None # Inicializa fora do loop

        while not rospy.is_shutdown():
            try:
                req = build_image_request(IMAGE_SOURCE_SPOT, quality_percent=75) # Spot img
                responses = self.image_client_spot.get_image([req])

                if not responses:
                    rospy.logwarn_throttle(5.0, "SPOT Localizer: ⚠️ Nenhuma imagem da garra recebida.")
                    rate.sleep()
                    continue

                img_resp_spot = responses[0]
                self.hand_cam_frame_name_spot = img_resp_spot.shot.frame_name_image_sensor
                
                cam_matrix_spot, dist_coeffs_spot = self._get_camera_intrinsics_spot(img_resp_spot)
                cv_image_spot = self._decode_image_spot(img_resp_spot)
                debug_img_spot = cv_image_spot.copy()


                corners, ids, rejected = aruco.detectMarkers(
                    cv_image_spot, self.aruco_dict, parameters=self.aruco_params
                )
                aruco.drawDetectedMarkers(debug_img_spot, corners, ids) # Desenha na cópia

                if ids is not None and self.target_id in ids:
                    idx = np.where(ids == self.target_id)[0][0]
                    marker_corners = corners[idx]

                    rospy.loginfo_throttle(1.0, f"SPOT Localizer: ✅ Aruco ID {self.target_id} encontrado pela câmera do Spot!")

                    rvecs, tvecs, _ = aruco.estimatePoseSingleMarkers(
                        [marker_corners], self.marker_size, cam_matrix_spot, dist_coeffs_spot
                    )
                    rvec_hca = rvecs[0][0] # HandCam_Spot -> Aruco
                    tvec_hca = tvecs[0][0] # HandCam_Spot -> Aruco
                    
                    rospy.loginfo_throttle(1.0, f"SPOT Localizer DBG: Detecção Spot TVEC: [{tvec_hca[0]:.3f}, {tvec_hca[1]:.3f}, {tvec_hca[2]:.3f}]")
                    cv2.drawFrameAxes(debug_img_spot, cam_matrix_spot, dist_coeffs_spot, rvec_hca, tvec_hca, self.marker_size * 0.75)

                    # Only calculate and publish map -> body
                    self._calculate_and_publish_map_to_body(tvec_hca, rvec_hca)
                else:
                    rospy.logwarn_throttle(2.0, f"SPOT Localizer: ⏳ Aruco ID {self.target_id} não encontrado pela câmera do Spot.")

            except Exception as e:
                rospy.logerr(f"SPOT Localizer: ❌ Erro no loop principal: {e}")
                rospy.sleep(1.0) # Evita spammar erro muito rápido

            finally:
                if debug_img_spot is not None: # Mostra a imagem de debug do Spot
                    pass #cv2.imshow(WINDOW_NAME_SPOT, debug_img_spot)
                #key = cv2.waitKey(1) & 0xFF # Comentado pra não travar sem GUI
                #if key == ord('q'):
                #    rospy.signal_shutdown("Janela de debug do Spot fechada com 'q'.")
            rate.sleep()

    def shutdown(self):
        rospy.loginfo("SPOT Localizer: 🧹 Limpando...")
        # cv2.destroyAllWindows() # Comentado pra não travar sem GUI
        if self.lease_keepalive:
            self.lease_keepalive.shutdown()
        rospy.loginfo("SPOT Localizer: ✌️ Tamo junto!")

def main():
    localizer = SpotArucoLocalizer()
    try:
        localizer.run()
    except rospy.ROSInterruptException:
        rospy.loginfo("🛑 Nó de Localização Aruco do Spot encerrado.")
    finally:
        localizer.shutdown()

if __name__ == '__main__':
    main()