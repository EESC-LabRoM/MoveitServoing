#!/usr/bin/env python3
# spot_yolo_realtime.py
import cv2
import numpy as np
from ultralytics import YOLO
import bosdyn.client
import bosdyn.client.util
from bosdyn.client.image import ImageClient
from bosdyn.api import image_pb2

def setup_spot(hostname, username, password):
    sdk = bosdyn.client.create_standard_sdk('SpotYOLORealtime')
    robot = sdk.create_robot(hostname)
    robot.authenticate(username, password)  # Correct method to authenticate
    robot.time_sync.wait_for_sync()
    image_client = robot.ensure_client(ImageClient.default_service_name)
    return image_client

def get_spot_frame(image_client, source):
    resp = image_client.get_image_from_sources([source])[0]
    # escolhe dtype
    dtype = np.uint16 if resp.shot.image.pixel_format == image_pb2.Image.PIXEL_FORMAT_DEPTH_U16 else np.uint8
    arr = np.frombuffer(resp.shot.image.data, dtype=dtype)
    if resp.shot.image.format == image_pb2.Image.FORMAT_RAW:
        img = arr.reshape(resp.shot.image.rows, resp.shot.image.cols)
    else:
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img

def main():
    hostname = "192.168.80.3"           # IP do Spot
    username = "admin"                  # ou como você autentica
    password = "spotadmin2017"          # se precisar
    image_source = "hand_color_image"   # câmera RGB da mão
    yolo_weights = "yolo11n.pt"

    print("⚡ Configurando Spot e modelo YOLO...")
    # setup único
    image_client = setup_spot(hostname, username, password)
    model = YOLO(yolo_weights)

    print("▶️ Iniciando loop de detecção (aperte 'q' pra sair)")
    while True:
        # 1) Captura frame
        img = get_spot_frame(image_client, image_source)
        # 2) prep pro YOLO
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        # 3) inferência
        results = model(img_rgb, verbose=False)
        # 4) desenha boxes
        for r in results:
            boxes = r.boxes.xyxy.cpu().numpy().astype(int)
            names = [r.names[int(c)] for c in r.boxes.cls.cpu().numpy()]
            confs = r.boxes.conf.cpu().numpy()
            for (x1, y1, x2, y2), name, conf in zip(boxes, names, confs):
                label = f"{name} {conf:.2f}"
                cv2.rectangle(img, (x1, y1), (x2, y2), (0,255,0), 2)
                cv2.putText(img, label, (x1, y1-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1)
        # 5) exibe
        cv2.imshow("YOLO Realtime on Spot", img)
        # 6) break se apertar 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()
    print("👋 Saindo...")

if __name__ == "__main__":
    main()
