# -*- coding: utf-8 -*-
"""
Script Python para detectar ArUco ID 42 com a câmera da garra do Spot
e mostrar a pose em um feed de vídeo com debug visual.
"""

import argparse
import sys
import time
import cv2
import numpy as np
import bosdyn.client
import bosdyn.client.util
from bosdyn.client.image import ImageClient
from bosdyn.client.robot_state import RobotStateClient
from bosdyn.api import image_pb2
import bosdyn.client.estop

# --- Constantes ---
ARUCO_ID_TO_FIND = 42
# Você pode precisar ajustar o dicionário ArUco dependendo do que você usa.
# O DICT_4X4_50 é bem comum.
ARUCO_DICTIONARY = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
ARUCO_PARAMETERS = cv2.aruco.DetectorParameters_create()
# Tamanho do marcador em metros (IMPORTANTE para a estimativa de pose correta!)
# Meça o seu marcador e coloque o valor aqui. Ex: 0.1 para 10cm.
MARKER_SIZE_METERS = 0.05
# Fonte da imagem da câmera da garra (pode variar um pouco, verifique no seu Spot)
GRIPPER_CAMERA_SOURCE = 'hand_color_image'

# --- Funções Auxiliares ---

def get_camera_intrinsics(image_response):
    """Extrai os parâmetros intrínsecos da câmera da resposta da imagem."""
    intrinsics = image_response.source.pinhole.intrinsics
    return np.array([
        [intrinsics.fx, 0, intrinsics.cx],
        [0, intrinsics.fy, intrinsics.cy],
        [0, 0, 1]
    ]), np.array([
        intrinsics.k1, intrinsics.k2, intrinsics.p1, intrinsics.p2, intrinsics.k3
    ])

def process_image(image_response, camera_matrix, dist_coeffs):
    """Processa a imagem, detecta ArUcos e desenha o debug."""
    if image_response.shot.image.pixel_format == image_pb2.Image.PIXEL_FORMAT_JPEG:
        try:
            image_data = image_response.shot.image.data
            np_arr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        except Exception as e:
            print(f"💥 Erro ao decodificar JPEG: {e}")
            return None
    else:
        print(f"Formato de pixel não suportado: {image_response.shot.image.pixel_format}")
        return None

    if img is None:
        print("💥 Imagem decodificada está vazia.")
        return None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    corners, ids, rejected = cv2.aruco.detectMarkers(gray, ARUCO_DICTIONARY,
                                                     parameters=ARUCO_PARAMETERS)

    if ids is not None and ARUCO_ID_TO_FIND in ids:
        print(f"🔥 Achei o ArUco ID {ARUCO_ID_TO_FIND}!")
        cv2.aruco.drawDetectedMarkers(img, corners, ids)

        # Filtra para pegar apenas o ID 42
        indices = np.where(ids == ARUCO_ID_TO_FIND)[0]
        corners_42 = [corners[i] for i in indices]
        ids_42 = np.array([[ARUCO_ID_TO_FIND] for _ in indices]) # Garante formato correto

        # Estima a pose para o ID 42
        rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
            corners_42, MARKER_SIZE_METERS, camera_matrix, dist_coeffs
        )

        for i in range(len(rvecs)):
            rvec = rvecs[i][0]
            tvec = tvecs[i][0]
            
            # Converte rvec para matriz de rotação (opcional, mas útil)
            rmat, _ = cv2.Rodrigues(rvec)

            print("-" * 30)
            print(f"  ID: {ids_42[i][0]}")
            print(f"  Translação (tvec) [m]: {tvec}")
            print(f"  Rotação (rvec) [rad]: {rvec}")
            # print(f"  Matriz de Rotação:\n{rmat}")
            print("-" * 30)

            # Desenha o eixo (X=vermelho, Y=verde, Z=azul)
            cv2.aruco.drawAxis(img, camera_matrix, dist_coeffs, rvec, tvec, MARKER_SIZE_METERS / 2)

    return img

def main(argv):
    """Função principal que conecta ao Spot e processa as imagens."""
    parser = argparse.ArgumentParser()
    bosdyn.client.util.add_base_arguments(parser)
    options = parser.parse_args(argv)

    try:
        sdk = bosdyn.client.create_standard_sdk('ArucoDetectorClient')
        robot = sdk.create_robot(options.hostname)
        bosdyn.client.util.authenticate(robot)
        robot.time_sync.wait_for_sync()

        print("🤖 Conectado ao Spot. Verificando E-Stop...")
        estop_client = robot.ensure_client(bosdyn.client.estop.EstopClient.default_service_name)
        estop_endpoint = bosdyn.client.estop.EstopEndpoint(estop_client, 'ArucoClient', 9.0)
        estop_endpoint.force_simple_setup()
        estop_keep_alive = bosdyn.client.estop.EstopKeepAlive(estop_endpoint)
        print("✅ E-Stop OK. Pegando clientes de estado e imagem...")

        robot_state_client = robot.ensure_client(RobotStateClient.default_service_name)
        image_client = robot.ensure_client(ImageClient.default_service_name)
        print("✅ Clientes OK.")

        # Liga o robô (se necessário)
        if not robot.is_powered_on():
            print("Ligando o robô...")
            robot.power_on(timeout_sec=20)
            assert robot.is_powered_on(), "💥 Robô não ligou."
            print("💡 Robô ligado.")

        # Pega a primeira imagem para obter os intrínsecos
        print(f"Pegando intrínsecos da câmera '{GRIPPER_CAMERA_SOURCE}'...")
        image_responses = image_client.get_image_from_sources([GRIPPER_CAMERA_SOURCE])
        
        if not image_responses:
             print(f"💥 Falha ao obter imagem da fonte: {GRIPPER_CAMERA_SOURCE}")
             return False

        image_response = image_responses[0] # Pega a primeira (e única) resposta
        
        if not image_response.source.pinhole:
            print(f"💥 A fonte '{GRIPPER_CAMERA_SOURCE}' não tem informações de pinhole (intrínsecos).")
            return False
            
        camera_matrix, dist_coeffs = get_camera_intrinsics(image_response)
        print("✅ Intrínsecos obtidos:")
        print(f"  Matriz da Câmera:\n{camera_matrix}")
        print(f"  Coeficientes de Distorção: {dist_coeffs}")


        print("\n🚀 Iniciando loop de captura e detecção. Pressione 'q' para sair.")
        
        cv2.namedWindow('Spot Gripper Aruco Debug', cv2.WINDOW_NORMAL)

        while True:
            image_responses = image_client.get_image_from_sources([GRIPPER_CAMERA_SOURCE])
            if not image_responses:
                print("⚠️  Nenhuma imagem recebida, tentando novamente...")
                time.sleep(0.1)
                continue

            image_response = image_responses[0]
            debug_img = process_image(image_response, camera_matrix, dist_coeffs)

            if debug_img is not None:
                cv2.imshow('Spot Gripper Aruco Debug', debug_img)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("Saindo...")
                break

        return True

    except bosdyn.client.RpcError as err:
        print(f"💥 Falha na comunicação com o robô: {err}")
        return False
    except Exception as exc:
        print(f"💥 Um erro inesperado aconteceu: {exc}")
        return False
    finally:
        # Garante que a janela do OpenCV seja fechada
        cv2.destroyAllWindows()
        print("Tudo limpo! 👌")


if __name__ == '__main__':
    if not main(sys.argv[1:]):
        sys.exit(1)
    sys.exit(0)