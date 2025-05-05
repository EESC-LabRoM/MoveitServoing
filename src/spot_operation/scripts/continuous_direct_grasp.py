#!/usr/bin/env python3
import rospy
import moveit_commander
from moveit_msgs.msg import JointConstraint, Constraints
from geometry_msgs.msg import PoseStamped
import subprocess
from std_msgs.msg import Int32
from abc import ABC, abstractmethod

import bosdyn.client
import bosdyn.client.util
from bosdyn.client.robot_command import RobotCommandBuilder, RobotCommandClient
from bosdyn.client.robot_state import RobotStateClient
from bosdyn.client.frame_helpers import ODOM_FRAME_NAME, get_a_tform_b
from bosdyn.client.math_helpers import SE3Pose, Quat
from bosdyn.client.lease import LeaseClient, LeaseWallet, add_lease_wallet_processors, LeaseKeepAlive
from bosdyn.client.lease import ResourceAlreadyClaimedError

import tf2_ros
import tf2_geometry_msgs
from geometry_msgs.msg import TransformStamped

import cv2
import numpy as np
import pandas as pd
from ultralytics import YOLO

from bosdyn.client.image import ImageClient
from bosdyn.client.manipulation_api_client import ManipulationApiClient
from bosdyn.api import geometry_pb2, manipulation_api_pb2, image_pb2


class RobotClientManager:
    """Gerencia conexões e clientes do Spot."""
    
    def __init__(self, hostname="192.168.80.3", username="admin", password="spotadmin2017"):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.sdk = None
        self.robot = None
        self.command_client = None
        self.state_client = None
        self.lease_client = None
        self.image_client = None
        self.manipulation_client = None
        self.lease_keepalive = None
        self.lease_wallet = None
        
    def connect(self):
        """Estabelece conexão com o robô e inicializa clientes necessários."""
        self.sdk = bosdyn.client.create_standard_sdk("SpotOperationSDK")
        self.robot = self.sdk.create_robot(self.hostname)
        self.robot.authenticate(self.username, self.password)
        self.robot.time_sync.wait_for_sync()
        
        if not self.robot.has_arm():
            rospy.logerr("Spot não possui braço. Abortando.")
            return False
            
        # Inicializa os clientes principais
        self.command_client = self.robot.ensure_client(RobotCommandClient.default_service_name)
        self.state_client = self.robot.ensure_client(RobotStateClient.default_service_name)
        self.lease_client = self.robot.ensure_client(LeaseClient.default_service_name)
        self.image_client = self.robot.ensure_client(ImageClient.default_service_name)
        self.manipulation_client = self.robot.ensure_client(ManipulationApiClient.default_service_name)
        
        return True
        
    def acquire_lease(self):
        """Adquire lease para controle do robô."""
        try:
            root_lease = self.lease_client.acquire()
        except ResourceAlreadyClaimedError:
            rospy.logwarn("Lease já em uso; forçando aquisição com take().")
            root_lease = self.lease_client.take()
            
        # Configura wallet e processadores
        self.lease_wallet = LeaseWallet()
        add_lease_wallet_processors(self.command_client, self.lease_wallet)
        self.lease_wallet.add(root_lease)
        
        # Mantém lease ativo
        self.lease_keepalive = LeaseKeepAlive(self.lease_client, self.lease_wallet,
                                           must_acquire=True, return_at_exit=False)
        return self.lease_keepalive
        
    def power_on(self):
        """Liga os motores do robô."""
        return self.robot.power_on(timeout_sec=20)
        
    def get_robot_state(self):
        """Obtém o estado atual do robô."""
        return self.state_client.get_robot_state()
        
    def send_arm_command(self, odom_T_hand):
        """Envia comando de posição para o braço."""
        arm_command = RobotCommandBuilder.arm_pose_command(
            odom_T_hand.x, odom_T_hand.y, odom_T_hand.z,
            odom_T_hand.rot.w, odom_T_hand.rot.x,
            odom_T_hand.rot.y, odom_T_hand.rot.z,
            ODOM_FRAME_NAME, 0.5
        )
        return self.command_client.robot_command(arm_command)
        
    def open_gripper(self):
        """Abre a garra do robô."""
        gripper_command = RobotCommandBuilder.claw_gripper_open_command()
        return self.command_client.robot_command(gripper_command)
        
    def close_gripper(self):
        """Fecha a garra do robô."""
        gripper_command = RobotCommandBuilder.claw_gripper_close_command()
        return self.command_client.robot_command(gripper_command)


class MoveItManager:
    """Gerencia a interface com o MoveIt para planejamento de movimento."""
    
    def __init__(self, group_name="manipulator", end_effector_link="arm_link_fngr"):
        self.group_name = group_name
        self.end_effector_link = end_effector_link
        moveit_commander.roscpp_initialize([])
        self.group = moveit_commander.MoveGroupCommander(group_name)
        self.group.set_end_effector_link(end_effector_link)
        rospy.loginfo("MoveIt inicializado: End-effector (%s) em relação a: %s",
                     self.end_effector_link, self.group.get_pose_reference_frame())
                     
    def apply_wrist_lock(self):
        """Aplica restrições nas juntas específicas para travar o punho."""
        names = self.group.get_active_joints()
        vals = self.group.get_current_joint_values()
        
        # Trava a junta arm_wr0
        idx_wr0 = names.index("arm_wr0")
        locked_value_wr0 = vals[idx_wr0]
        rospy.loginfo("🔒 Travando arm_wr0 em %.3f rad", locked_value_wr0)
        jc_wr0 = JointConstraint(joint_name="arm_wr0",
                                 position=locked_value_wr0,
                                 tolerance_above=0.0,
                                 tolerance_below=0.0,
                                 weight=1.0)
        
        # Trava a junta arm_wr1
        idx_wr1 = names.index("arm_wr1")
        locked_value_wr1 = vals[idx_wr1]
        rospy.loginfo("🔒 Travando arm_wr1 em %.3f rad", locked_value_wr1)
        jc_wr1 = JointConstraint(joint_name="arm_wr1",
                                 position=locked_value_wr1,
                                 tolerance_above=0.0,
                                 tolerance_below=0.0,
                                 weight=1.0)
        
        # Aplica as restrições
        cs = Constraints()
        cs.joint_constraints.extend([jc_wr0, jc_wr1])
        self.group.set_path_constraints(cs)
        
    def get_current_pose(self):
        """Obtém a pose atual do end-effector."""
        rospy.sleep(0.1)  # Pequena pausa para garantir atualização
        return self.group.get_current_pose().pose


class TFManager:
    """Gerencia transformações de coordenadas usando TF."""
    
    def __init__(self):
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer)
        
    def get_pose(self, target_frame="wrist", reference_frame="world", timeout=1.0):
        """Obtém a pose de um frame em relação a outro usando TF."""
        try:
            transform = self.tf_buffer.lookup_transform(
                reference_frame, target_frame, rospy.Time(0), rospy.Duration(timeout)
            )
            pose = PoseStamped()
            pose.header = transform.header
            pose.pose.position.x = transform.transform.translation.x
            pose.pose.position.y = transform.transform.translation.y
            pose.pose.position.z = transform.transform.translation.z
            pose.pose.orientation = transform.transform.rotation
            return pose.pose
        except Exception as e:
            rospy.logwarn(f"❗ TF lookup falhou: {e}")
            return None


class ObjectDetector:
    """Gerencia detecção de objetos usando YOLO."""
    
    def __init__(self, model_path, allowed_objects_csv):
        """
        Inicializa detector com modelo YOLO e CSV de objetos permitidos.
        
        Args:
            model_path: Caminho para o arquivo do modelo YOLO
            allowed_objects_csv: Caminho para CSV com objetos permitidos e prioridades
        """
        self.model = YOLO(model_path)
        self.allowed_objects = pd.read_csv(allowed_objects_csv)
        self.allowed_objects['class'] = self.allowed_objects['class'].str.strip().str.lower()
        
    def detect_objects(self, image):
        """Detecta objetos na imagem e retorna informações relevantes."""
        results = self.model(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        boxes = results[0].boxes.xyxy.cpu().numpy()
        classes = results[0].boxes.cls.cpu().numpy().astype(int)
        names = [results[0].names[c].lower() for c in classes]
        
        return boxes, classes, names
        
    def filter_allowed_objects(self, boxes, names):
        """Filtra objetos detectados mantendo apenas os permitidos."""
        candidates = []
        
        for i, name in enumerate(names):
            df = self.allowed_objects[self.allowed_objects['class'] == name]
            if df.empty:
                continue
                
            priority = int(df['priority'].iloc[0])
            x1, y1, x2, y2 = boxes[i]
            area = (x2 - x1) * (y2 - y1)
            
            # Armazena (prioridade, -área, índice) para ordenação
            candidates.append((priority, -area, i))
            
        # Ordena por prioridade (menor é melhor) e depois por área (maior é melhor)
        candidates.sort()
        return candidates


class GraspStrategyBase(ABC):
    """Interface base para estratégias de grasp."""
    
    @abstractmethod
    def execute(self, robot_manager):
        """
        Executa a estratégia de grasp.
        
        Args:
            robot_manager: Gerenciador de clientes do robô
            
        Returns:
            bool: True se o grasp foi bem-sucedido, False caso contrário
        """
        pass


class YOLOGraspStrategy(GraspStrategyBase):
    """Estratégia de grasp baseada em detecção YOLO."""
    
    def __init__(self, detector, image_source="hand_color_image"):
        self.detector = detector
        self.image_source = image_source
        
    def execute(self, robot_manager):
        """Executa grasp com base na detecção YOLO."""
        # Captura imagem do robô
        resp = robot_manager.image_client.get_image_from_sources([self.image_source])[0]
        arr = np.frombuffer(resp.shot.image.data, dtype=np.uint8)
        image = (arr.reshape(resp.shot.image.rows, resp.shot.image.cols) 
               if resp.shot.image.format == image_pb2.Image.FORMAT_RAW
               else cv2.imdecode(arr, -1))
            
        # Detecta e filtra objetos
        boxes, _, names = self.detector.detect_objects(image)
        candidates = self.detector.filter_allowed_objects(boxes, names)
        
        if not candidates:
            rospy.logwarn("[GRASP] Nenhum objeto permitido detectado na imagem.")
            return False
            
        # Seleciona o melhor candidato
        _, _, selected_idx = candidates[0]
        x1, y1, x2, y2 = boxes[selected_idx]
        cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
        
        # Executa grasp na posição determinada
        pick = manipulation_api_pb2.PickObjectInImage(
            pixel_xy=geometry_pb2.Vec2(x=cx, y=cy),
            transforms_snapshot_for_camera=resp.shot.transforms_snapshot,
            frame_name_image_sensor=resp.shot.frame_name_image_sensor,
            camera_model=resp.source.pinhole
        )
        
        req = manipulation_api_pb2.ManipulationApiRequest(pick_object_in_image=pick)
        cmd_resp = robot_manager.manipulation_client.manipulation_api_command(req, timeout=5.0)
        
        # Monitora feedback
        result = self._monitor_grasp_feedback(robot_manager, cmd_resp)
        return result
        
    def _monitor_grasp_feedback(self, robot_manager, cmd_resp, poll_interval=0.2):
        """Monitora o feedback do comando de grasp."""
        while True:
            fb_req = manipulation_api_pb2.ManipulationApiFeedbackRequest(
                manipulation_cmd_id=cmd_resp.manipulation_cmd_id
            )
            fb = robot_manager.manipulation_client.manipulation_api_feedback_command(fb_req)
            state = manipulation_api_pb2.ManipulationFeedbackState.Name(fb.current_state)
            rospy.loginfo(f"[GRASP] Estado = {state}")
            
            if fb.current_state == manipulation_api_pb2.MANIP_STATE_GRASP_SUCCEEDED:
                return True
            elif fb.current_state == manipulation_api_pb2.MANIP_STATE_GRASP_FAILED:
                return False
                
            rospy.sleep(poll_interval)


class GraspManager:
    """Gerencia diferentes estratégias de grasp."""
    
    def __init__(self):
        self.strategies = {}
        self.last_used_strategy = None
        self.success_count = {}
        self.attempt_count = {}
        
    def register_strategy(self, name, strategy):
        """Registra uma nova estratégia de grasp."""
        self.strategies[name] = strategy
        self.success_count[name] = 0
        self.attempt_count[name] = 0
        
    def execute_grasp(self, strategy_name, robot_manager):
        """
        Executa a estratégia de grasp especificada.
        
        Args:
            strategy_name: Nome da estratégia a ser executada
            robot_manager: Gerenciador de clientes do robô
            
        Returns:
            bool: True se o grasp foi bem-sucedido, False caso contrário
        """
        if strategy_name not in self.strategies:
            rospy.logerr(f"Estratégia '{strategy_name}' não encontrada.")
            return False
            
        strategy = self.strategies[strategy_name]
        self.last_used_strategy = strategy_name
        self.attempt_count[strategy_name] += 1
        
        # Executa a estratégia e registra resultado
        result = strategy.execute(robot_manager)
        if result:
            self.success_count[strategy_name] += 1
            
        # Loga estatísticas de sucesso
        success_rate = self.success_count[strategy_name] / self.attempt_count[strategy_name] * 100
        rospy.loginfo(f"Estratégia '{strategy_name}' - Taxa de sucesso: {success_rate:.1f}% ({self.success_count[strategy_name]}/{self.attempt_count[strategy_name]})")
        
        return result
        
    def get_success_rates(self):
        """Retorna as taxas de sucesso de todas as estratégias registradas."""
        rates = {}
        for name in self.strategies:
            if self.attempt_count[name] > 0:
                rates[name] = self.success_count[name] / self.attempt_count[name]
            else:
                rates[name] = 0.0
        return rates


class SpotController:
    """Controlador principal do Spot."""
    
    def __init__(self, spot_hostname="192.168.80.3", model_path="/root/ws_moveit/src/spot_operation/scripts/yolo11n.pt", 
                 allowed_objects_csv="/root/ws_moveit/src/spot_operation/config/allowed_objects.csv"):
        # Inicializa ROS
        rospy.init_node("continuous_moveit_pose_to_spot_real", anonymous=True)
        
        # Configuração de gestos
        self.current_gesture = 0
        self.manipulation_mode = False
        rospy.Subscriber("/hand_gesture", Int32, self._gesture_callback)
        
        # Inicializa gerenciadores
        self.tf_manager = TFManager()
        self.moveit_manager = MoveItManager()
        
        # Aplica restrições de juntas
        self.moveit_manager.apply_wrist_lock()
            
        # Conecta ao Spot
        self.robot_manager = RobotClientManager(hostname=spot_hostname)
        
        if not self.robot_manager.connect():
            rospy.logerr("Falha ao conectar ao Spot. Abortando.")
            return
            
        # Inicializa detector de objetos
        self.object_detector = ObjectDetector(
            model_path=model_path,
            allowed_objects_csv=allowed_objects_csv
        )
        
        # Inicializa gerenciador de grasp
        self.grasp_manager = GraspManager()
        
        # Registra múltiplas estratégias de grasp com diferentes fontes de imagem
        # Câmera principal (frontal)
        front_grasp = YOLOGraspStrategy(
            detector=self.object_detector,
            image_source="hand_color_image"
        )
        self.grasp_manager.register_strategy("front_yolo", front_grasp)
        
        # Câmera lateral (se disponível)
        side_grasp = YOLOGraspStrategy(
            detector=self.object_detector,
            image_source="frontleft_fisheye_image"
        )
        self.grasp_manager.register_strategy("side_yolo", side_grasp)
        
        # Estratégia padrão
        self.default_grasp_strategy = "front_yolo"
        # Estratégia fallback (para usar quando a principal falhar)
        self.fallback_grasp_strategy = "side_yolo"
        
    def _gesture_callback(self, msg):
        """Callback para mensagens de gestos."""
        self.current_gesture = msg.data
        
    def run(self):
        """Executa o loop principal de controle."""
        # Adquire lease
        with self.robot_manager.acquire_lease():
            # Liga o robô
            self.robot_manager.power_on()
            rospy.loginfo("Robô ligado. Iniciando sincronização contínua...")
            
            # Loop principal
            self._control_loop()
    
    def _enter_manipulation_mode(self):
        """Entra no modo de manipulação após um grasp bem-sucedido."""
        self.manipulation_mode = True
        rospy.loginfo("🤖 Entrando no modo de MANIPULAÇÃO. Aguardando gesto '0' para liberar objeto...")
    
    def _exit_manipulation_mode(self):
        """Sai do modo de manipulação e retorna ao modo normal."""
        # Abre a garra por 3 segundos
        rospy.loginfo("Liberando objeto: Abrindo garra por 3 segundos...")
        self.robot_manager.open_gripper()
        rospy.sleep(3.0)
        
        # Fecha a garra novamente
        rospy.loginfo("Fechando garra...")
        self.robot_manager.close_gripper()
        
        # Sai do modo de manipulação
        self.manipulation_mode = False
        rospy.loginfo("🤖 Saindo do modo de MANIPULAÇÃO. Retornando ao modo normal.")
            
    def _control_loop(self):
        """Loop principal de controle."""
        rate = rospy.Rate(2)  # 2 Hz como no código original
        
        while not rospy.is_shutdown():
            # Verifica se estamos no modo de manipulação
            if self.manipulation_mode:
                # Verifica se recebemos o gesto para liberar o objeto
                if self.current_gesture == 0:
                    self._exit_manipulation_mode()
                else:
                    # Continua no modo de manipulação
                    # Obtém pose da simulação
                    sim_pose = self.tf_manager.get_pose()
                    if sim_pose is not None:
                        # Obtém transformação do corpo para a mão
                        robot_state = self.robot_manager.get_robot_state()
                        odom_T_body = get_a_tform_b(
                            robot_state.kinematic_state.transforms_snapshot,
                            ODOM_FRAME_NAME, "body"
                        )
                        
                        # Aplica transformação da simulação
                        flat_body_T_hand = SE3Pose(
                            x=sim_pose.position.x,
                            y=sim_pose.position.y,
                            z=sim_pose.position.z,
                            rot=Quat(
                                w=sim_pose.orientation.w,
                                x=sim_pose.orientation.x,
                                y=sim_pose.orientation.y,
                                z=sim_pose.orientation.z
                            )
                        )
                        
                        # Calcula pose final
                        odom_T_hand = odom_T_body * flat_body_T_hand
                        
                        # Envia comando para o braço
                        self.robot_manager.send_arm_command(odom_T_hand)
                        
                        rospy.loginfo("Modo MANIPULAÇÃO: Comando enviado: Pose alvo = [%.3f, %.3f, %.3f]",
                                     odom_T_hand.x, odom_T_hand.y, odom_T_hand.z)
                
                rate.sleep()
                continue
            
            # Modo normal (não está no modo de manipulação)
            # Verifica gestos para iniciar grasp
            if self.current_gesture == 1:
                rospy.loginfo("✋ Gesto de agarrar detectado!")
                
                # Tenta executar a estratégia primária
                result = self.grasp_manager.execute_grasp(self.default_grasp_strategy, self.robot_manager)
                
                # Se falhar, tenta o fallback
                if not result:
                    rospy.logwarn("Grasp primário falhou. Tentando estratégia alternativa...")
                    result = self.grasp_manager.execute_grasp(self.fallback_grasp_strategy, self.robot_manager)
                    if not result:
                        rospy.logerr("Todas as estratégias de grasp falharam.")
                    else:
                        rospy.loginfo("Grasp alternativo concluído com sucesso!")
                        # Entra no modo de manipulação após grasp bem-sucedido
                        self._enter_manipulation_mode()
                else:
                    rospy.loginfo("Grasp primário concluído com sucesso!")
                    # Entra no modo de manipulação após grasp bem-sucedido
                    self._enter_manipulation_mode()
                
                # Reseta o gesto apenas se não entramos no modo de manipulação
                if not self.manipulation_mode:
                    self.current_gesture = 0
                    
                rospy.sleep(1.0)
                continue
                
            # Obtém pose da simulação
            sim_pose = self.tf_manager.get_pose()
            if sim_pose is None:
                rospy.logwarn("⚠️ Não foi possível obter a pose do wrist.")
                rate.sleep()
                continue
                
            # Obtém transformação do corpo para a mão
            robot_state = self.robot_manager.get_robot_state()
            odom_T_body = get_a_tform_b(
                robot_state.kinematic_state.transforms_snapshot,
                ODOM_FRAME_NAME, "body"
            )
            
            # Aplica transformação da simulação
            flat_body_T_hand = SE3Pose(
                x=sim_pose.position.x,
                y=sim_pose.position.y,
                z=sim_pose.position.z,
                rot=Quat(
                    w=sim_pose.orientation.w,
                    x=sim_pose.orientation.x,
                    y=sim_pose.orientation.y,
                    z=sim_pose.orientation.z
                )
            )
            
            # Calcula pose final
            odom_T_hand = odom_T_body * flat_body_T_hand
            
            # Envia comando para o braço
            self.robot_manager.send_arm_command(odom_T_hand)
            
            rospy.loginfo("Comando enviado: Pose alvo = [%.3f, %.3f, %.3f]",
                         odom_T_hand.x, odom_T_hand.y, odom_T_hand.z)
                         
            rate.sleep()


def main():
    """Função principal."""
    # Inicializa e executa o controlador
    controller = SpotController()
    controller.run()


if __name__ == "__main__":
    try:
        main()
    except rospy.ROSInterruptException:
        pass