#!/usr/bin/env python3

import rospy
# import cv2 # <--- REMOVIDO se não for usar para debug visual
# import cv2.aruco as aruco # <--- Mantido para detecção
import cv2.aruco as aruco # Mantido para detecção, cv2 é necessário para aruco
import cv2 # cv2 é necessário para aruco e CvBridge

import numpy as np
import tf2_ros
from geometry_msgs.msg import TransformStamped
from sensor_msgs.msg import Image, CameraInfo
from cv_bridge import CvBridge, CvBridgeError
from scipy.spatial.transform import Rotation as R
import math
import threading # Necessário para self.transform_lock

# --- Configurações ---
ARUCO_DICTIONARY_NAME = aruco.DICT_4X4_50
ARUCO_MARKER_SIZE_METERS = 0.2 # 🚨 SEU TAMANHO DE ARUCO AQUI (0.2m = 20cm) 🚨
TARGET_ARUCO_ID = 0

ZED_IMAGE_TOPIC = "/zed2i/zed_node/left/image_rect_color"
ZED_CAMERA_INFO_TOPIC = "/zed2i/zed_node/left/camera_info"

ZED_OPTICAL_FRAME_DEFAULT = "zed2i_left_camera_optical_frame"
ARUCO_CHILD_FRAME = f"aruco_marker_{TARGET_ARUCO_ID}"

PUBLISH_RATE_HZ = 10 # Taxa de publicação da ÚLTIMA TF VÁLIDA
# WINDOW_NAME_ZED = "ZED Aruco Detection 🔥" # <--- REMOVIDO

class ZEDArucoTFPublisherContinuousNoGUI:
    def __init__(self):
        rospy.init_node('zed_aruco_tf_publisher_continuous_no_gui', anonymous=True)
        rospy.loginfo(f"🔥 Iniciando Nó ZED Aruco TF Publisher (Contínuo, Sem GUI) para ID {TARGET_ARUCO_ID}...")

        self.aruco_dict = aruco.getPredefinedDictionary(ARUCO_DICTIONARY_NAME)
        try:
            self.aruco_params = aruco.DetectorParameters_create()
        except AttributeError:
            try:
                self.aruco_params = aruco.DetectorParameters()
                rospy.logwarn("Usando aruco.DetectorParameters()")
            except AttributeError:
                rospy.logerr("❌ Aruco 'DetectorParameters' ou '_create' não encontrado!")
                rospy.signal_shutdown("OpenCV Contrib não encontrado")
                return

        self.marker_size = ARUCO_MARKER_SIZE_METERS
        if self.marker_size <= 0:
            rospy.logerr("🚫 Tamanho do Aruco inválido!")
            rospy.signal_shutdown("Configuração inválida.")
            return

        self.bridge = CvBridge()
        self.tf_broadcaster = tf2_ros.TransformBroadcaster()

        self.camera_matrix = None
        self.dist_coeffs = None
        self.zed_optical_frame_actual = ZED_OPTICAL_FRAME_DEFAULT
        
        self.last_valid_tf = None
        self.transform_lock = threading.Lock()

        self.translation_buffer = []
        self.rotation_buffer_quat = []
        self.smoothing_buffer_size = 5

        self.cam_info_sub = rospy.Subscriber(ZED_CAMERA_INFO_TOPIC, CameraInfo, self.camera_info_callback)
        self.image_sub = None 

        rospy.loginfo(f"Aguardando CameraInfo em: {ZED_CAMERA_INFO_TOPIC}...")
        
        # cv2.namedWindow(WINDOW_NAME_ZED, cv2.WINDOW_NORMAL) # <--- REMOVIDO
        # cv2.resizeWindow(WINDOW_NAME_ZED, 640, 480) # <--- REMOVIDO

        self.tf_publish_timer = rospy.Timer(rospy.Duration(1.0 / PUBLISH_RATE_HZ), self.publish_last_tf_callback)
        rospy.loginfo(f"Timer de publicação de TF configurado para {PUBLISH_RATE_HZ} Hz.")


    def camera_info_callback(self, msg):
        with self.transform_lock:
            if self.camera_matrix is None: 
                self.camera_matrix = np.array(msg.K).reshape((3, 3))
                self.dist_coeffs = np.array(msg.D)
                self.zed_optical_frame_actual = msg.header.frame_id
                rospy.loginfo(f"✅ Info da ZED recebida! Frame Óptico: '{self.zed_optical_frame_actual}'")
                
                if self.image_sub is None:
                    self.image_sub = rospy.Subscriber(ZED_IMAGE_TOPIC, Image, self.image_callback)
                    rospy.loginfo(f"Escutando Imagem em: {ZED_IMAGE_TOPIC}")
                    rospy.loginfo(f"Pronto para publicar TF: {self.zed_optical_frame_actual} -> {ARUCO_CHILD_FRAME}")
                
                self.cam_info_sub.unregister()

    def image_callback(self, msg):
        rospy.logdebug_throttle(0.5, "ZED DBG: image_callback chamado!") 

        if self.camera_matrix is None or self.dist_coeffs is None:
            rospy.logwarn_throttle(2.0, "🚦 Esperando info da ZED...")
            return

        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        except CvBridgeError as e:
            rospy.logerr(f"Erro CvBridge: {e}")
            return
        
        # debug_image = cv_image.copy() # <--- Não precisa mais se não for mostrar
        rospy.logdebug_throttle(0.5, "ZED DBG: Imagem convertida. Detectando marcadores...")
        corners, ids, rejected = aruco.detectMarkers(cv_image, self.aruco_dict, parameters=self.aruco_params) # Usa cv_image direto
        
        if ids is not None:
            rospy.loginfo_throttle(1.0, f"ZED DBG: IDs detectados nesta imagem: {ids.flatten().tolist()}")
        else:
            rospy.logdebug_throttle(1.0, "ZED DBG: Nenhum ID detectado nesta imagem.")

        # aruco.drawDetectedMarkers(debug_image, corners, ids) # <--- REMOVIDO

        if ids is not None and TARGET_ARUCO_ID in ids:
            idx = np.where(ids == TARGET_ARUCO_ID)[0][0]
            marker_corners = corners[idx]

            rvecs, tvecs, _ = aruco.estimatePoseSingleMarkers(
                [marker_corners], self.marker_size, self.camera_matrix, self.dist_coeffs
            )
            rvec = rvecs[0][0]
            tvec = tvecs[0][0]

            rospy.loginfo_throttle(1.0, f"ZED: Aruco ID {TARGET_ARUCO_ID} detectado! "
                                        f"TVEC: [{tvec[0]:.3f}, {tvec[1]:.3f}, {tvec[2]:.3f}]")
            # cv2.drawFrameAxes(debug_image, self.camera_matrix, self.dist_coeffs, rvec, tvec, self.marker_size * 0.75) # <--- REMOVIDO

            t = TransformStamped()
            t.header.frame_id = self.zed_optical_frame_actual
            t.child_frame_id = ARUCO_CHILD_FRAME
            t.transform.translation.x = tvec[0]
            t.transform.translation.y = tvec[1]
            t.transform.translation.z = tvec[2]

            try:
                rvec_flat = rvec.flatten()
                if rvec_flat.shape != (3,):
                    rospy.logwarn_throttle(5, f"ZED: RVEC formato inesperado: {rvec_flat.shape}")
                else:
                    rotation = R.from_rotvec(rvec_flat)
                    quat = rotation.as_quat()
                    norm_sq = np.sum(np.square(quat))
                    if not (np.isnan(quat).any() or np.isinf(quat).any() or math.isclose(norm_sq, 0.0, abs_tol=1e-6) or not math.isclose(norm_sq, 1.0, abs_tol=1e-3)):
                        t.transform.rotation.x = quat[0]
                        t.transform.rotation.y = quat[1]
                        t.transform.rotation.z = quat[2]
                        t.transform.rotation.w = quat[3]
                        
                        with self.transform_lock:
                            self.last_valid_tf = t
                        rospy.loginfo_throttle(0.2, f"ZED DBG: self.last_valid_tf ATUALIZADO para Aruco ID {TARGET_ARUCO_ID}!")
                    else:
                        rospy.logwarn_throttle(5, f"ZED: Quatérnion inválido: {quat}, Norma^2: {norm_sq}. last_valid_tf NÃO atualizado.")
            except ValueError as ve:
                rospy.logwarn_throttle(5, f"ZED: Erro de VALOR convertendo RVEC: {ve}, RVEC: {rvec.flatten()}")
            except Exception as e:
                rospy.logwarn_throttle(5, f"ZED: Erro GERAL convertendo rotação: {e}")
        else:
            rospy.logwarn_throttle(1.0, f"ZED: Aruco ID {TARGET_ARUCO_ID} NÃO encontrado nesta imagem.")

        # cv2.imshow(WINDOW_NAME_ZED, debug_image) # <--- REMOVIDO
        # cv2.waitKey(1) # <--- REMOVIDO (não tem mais imshow pra processar)

    def publish_last_tf_callback(self, event):
        with self.transform_lock:
            if self.last_valid_tf:
                self.last_valid_tf.header.stamp = rospy.Time.now()
                self.tf_broadcaster.sendTransform(self.last_valid_tf)
                rospy.logdebug_throttle(1.0, f"SMOOTH TF: {self.last_valid_tf.header.frame_id} -> {self.last_valid_tf.child_frame_id} publicada")
            else:
                rospy.logdebug_throttle(5.0, "SMOOTH TF: Nenhuma TF suavizada para publicar ainda.")

    def run(self):
        rospy.spin()
        # cv2.destroyAllWindows() # <--- REMOVIDO

if __name__ == '__main__':
    # import threading # Já está no topo
    try:
        publisher = ZEDArucoTFPublisherContinuousNoGUI()
        publisher.run()
    except rospy.ROSInterruptException:
        rospy.loginfo("🛑 ZED Aruco TF Publisher (Contínuo, Sem GUI) encerrado.")
    # finally: # <--- REMOVIDO o destroyAllWindows daqui também
        # cv2.destroyAllWindows()