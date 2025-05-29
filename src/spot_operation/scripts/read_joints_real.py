#!/usr/bin/env python3

import sys
import rospy
import bosdyn.client
import bosdyn.client.util
from bosdyn.client.robot_state import RobotStateClient
from bosdyn.client.frame_helpers import get_a_tform_b # Para pegar TFs do SDK

import tf2_ros # Para publicar TFs
from geometry_msgs.msg import TransformStamped
from sensor_msgs.msg import JointState # Para publicar o estado das juntas

SPOT_HOSTNAME = "192.168.80.3"
SPOT_USERNAME = "admin"
SPOT_PASSWORD = "spotadmin2017"

# --- Nomes dos Frames (CRUCIAL VERIFICAR!) ---
ODOMETRY_FRAME_ID = "odom"  # Frame "pai" da odometria (ex: odom, vision_odom)
BASE_LINK_FRAME_ID = "body" # Frame base do robô (ex: body, base_link do URDF)

# --- Nomes das Juntas (CRUCIAL VERIFICAR COM SEU URDF!) ---
# Se seu URDF usa prefixos (ex: <param name="tf_prefix" value="spot"/>),
# os URDF_JOINT_NAMES devem incluir esse prefixo.
SDK_JOINT_NAMES = [
    "arm0.sh0", "arm0.sh1", "arm0.el0",
    "arm0.el1", "arm0.wr0", "arm0.wr1",
    "arm0.f1x"  # <--- ✅ ADICIONADO O NOME DO SDK!
]
URDF_JOINT_NAMES = [
    "arm_sh0", "arm_sh1", "arm_el0",
    "arm_el1", "arm_wr0", "arm_wr1",
    "arm_f1x"  # <--- ✅ ADICIONADO O NOME DO URDF! (Confirme se é esse mesmo)
]
# Garanta que as listas tenham o mesmo tamanho e ordem correspondente
if len(SDK_JOINT_NAMES) != len(URDF_JOINT_NAMES):
    rospy.logerr("ERRO CRÍTICO: SDK_JOINT_NAMES e URDF_JOINT_NAMES têm tamanhos diferentes!")
    sys.exit(1) # Não continua se os nomes não baterem em quantidade

SDK_TO_URDF_JOINT_MAP = dict(zip(SDK_JOINT_NAMES, URDF_JOINT_NAMES))

PUBLISH_RATE = 1000 # Hz

def main():
    rospy.init_node("spot_state_publisher", anonymous=True)

    tf_broadcaster = tf2_ros.TransformBroadcaster()
    joint_state_publisher = rospy.Publisher('/joint_states', JointState, queue_size=1)

    rospy.loginfo(f"Tentando conectar ao Spot em {SPOT_HOSTNAME}...")
    bosdyn.client.util.setup_logging(False) # Menos verboso no log do ROS
    sdk = bosdyn.client.create_standard_sdk("SpotStatePublisherSDK")
    try:
        robot = sdk.create_robot(SPOT_HOSTNAME)
        robot.authenticate(SPOT_USERNAME, SPOT_PASSWORD)
        robot.time_sync.wait_for_sync()
        state_client = robot.ensure_client(RobotStateClient.default_service_name)
        rospy.loginfo("✅ Conectado ao Spot!")
    except Exception as e:
        rospy.logerr(f"❌ Falha ao conectar ao Spot: {e}")
        return

    rospy.loginfo("📢 Publicando TF de odometria e /joint_states do Spot...")
    rate = rospy.Rate(PUBLISH_RATE)

    printed_sdk_joint_names = False 

    while not rospy.is_shutdown():
        try:
            robot_state = state_client.get_robot_state()
        except Exception as e:
            rospy.logerr_throttle(5.0, f"Erro ao obter estado do Spot: {e}")
            rate.sleep()
            continue

        current_time = rospy.Time.now()

        # =============== Bloco 1: Publicar TF de Odometria (odom -> body) ===============
        # try:
        #     snapshot = robot_state.kinematic_state.transforms_snapshot
        #     odom_T_body_sdk = get_a_tform_b(snapshot, ODOMETRY_FRAME_ID, BASE_LINK_FRAME_ID)

        #     if odom_T_body_sdk:
        #         t = TransformStamped()
        #         t.header.stamp = current_time
        #         t.header.frame_id = ODOMETRY_FRAME_ID
        #         t.child_frame_id = BASE_LINK_FRAME_ID
        #         t.transform.translation.x = odom_T_body_sdk.x
        #         t.transform.translation.y = odom_T_body_sdk.y
        #         t.transform.translation.z = odom_T_body_sdk.z
        #         t.transform.rotation.x = odom_T_body_sdk.rot.x
        #         t.transform.rotation.y = odom_T_body_sdk.rot.y
        #         t.transform.rotation.z = odom_T_body_sdk.rot.z
        #         t.transform.rotation.w = odom_T_body_sdk.rot.w
        #         tf_broadcaster.sendTransform(t)
        #     else:
        #         rospy.logwarn_throttle(5.0, f"⚠️ Não foi possível obter a TF {ODOMETRY_FRAME_ID} -> {BASE_LINK_FRAME_ID} do SDK.")

        # except Exception as e:
        #     rospy.logwarn_throttle(5.0, f"Erro ao processar/publicar TF de odometria: {e}")

        # =============== Bloco 2: Publicar /joint_states ===============
        joint_state_msg = JointState()
        joint_state_msg.header.stamp = current_time
        
        # Preenche com as juntas que a gente mapeou
        # Idealmente, iterar por todas as juntas do robot_state.kinematic_state.joint_states
        # e verificar se o nome do SDK está no nosso mapa.
        found_joint_names = []
        found_joint_positions = []

        for sdk_joint_info in robot_state.kinematic_state.joint_states:
            sdk_joint_name = sdk_joint_info.name
            if sdk_joint_name in SDK_TO_URDF_JOINT_MAP:
                urdf_joint_name = SDK_TO_URDF_JOINT_MAP[sdk_joint_name]
                found_joint_names.append(urdf_joint_name)
                found_joint_positions.append(sdk_joint_info.position.value)
                # Se quiser velocidade e esforço:
                # joint_state_msg.velocity.append(sdk_joint_info.velocity.value)
                # joint_state_msg.effort.append(sdk_joint_info.effort.value)
        
        if found_joint_names:
            joint_state_msg.name = found_joint_names
            joint_state_msg.position = found_joint_positions
            joint_state_publisher.publish(joint_state_msg)
        else:
            rospy.logwarn_throttle(5.0, "⚠️ Nenhuma junta mapeada encontrada no estado do Spot.")

        rate.sleep()

if __name__ == '__main__':
    try:
        main()
    except rospy.ROSInterruptException:
        rospy.loginfo("🛑 Spot State Publisher encerrado.")
    except Exception as e:
        rospy.logfatal(f"❌ Erro fatal no Spot State Publisher: {e}")