#!/usr/bin/env bash
set -e

# ================================================================
# Variáveis de configuração
# ================================================================
CONTAINER_NAME="zed_spot_noetic_container"  # <- updated container name
IMAGE_NAME="zed-spot-noetic:latest"         # <- updated image name
WORKSPACE_DIR="$HOME/ws_moveit"
HOST_DISPLAY=${DISPLAY:-:0}

# Cria workspace se não existir
mkdir -p "$WORKSPACE_DIR"

# ================================================================
# Permissões X11
# ================================================================
echo "🔓 Allowing X11 local Docker connections..."
xhost +local:docker

# ================================================================
# Detecta /dev/video* e monta cada um
# ================================================================
echo "🔍 Detecting video devices..."
camera_devices=()
for dev in /dev/video*; do
  if [ -e "$dev" ]; then
    echo "    • Found camera device: $dev"
    camera_devices+=(--device="${dev}:${dev}")
  fi
done
if [ ${#camera_devices[@]} -eq 0 ]; then
  echo "⚠️  Warning: no /dev/video* found on host!"
fi

# ================================================================
# Gera entrypoint temporário (mesma lógica de antes)
# ================================================================
TEMP_ENTRYPOINT="$WORKSPACE_DIR/tmp_entrypoint.sh"
cat > "$TEMP_ENTRYPOINT" << 'EOF'
#!/usr/bin/env bash
set -e

# Ajusta DISPLAY e Qt para GUI
export DISPLAY=$DISPLAY
export QT_X11_NO_MITSHM=1
export XDG_RUNTIME_DIR=/tmp/runtime-root

# Sourcing ROS
source /opt/ros/noetic/setup.bash
if [ -f "/root/ws_moveit/devel/setup.bash" ]; then
  source /root/ws_moveit/devel/setup.bash
fi

# Rebuild opcional
if [ "$1" = "--rebuild" ]; then
  echo "🔧 Rebuilding workspace..."
  cd /root/ws_moveit
  catkin build
  source /root/ws_moveit/devel/setup.bash
  shift
fi

# Executa comando passado
exec "$@"
EOF
chmod +x "$TEMP_ENTRYPOINT"

# ================================================================
# Roda o container
# ================================================================
echo "🚀 Starting container '$CONTAINER_NAME' from image '$IMAGE_NAME'..."
docker run -it --rm \
  --gpus all \
  --name "$CONTAINER_NAME" \
  --net=host \
  --privileged \
  --group-add video \
  -e DISPLAY="$HOST_DISPLAY" \
  -e QT_X11_NO_MITSHM=1 \
  -e XDG_RUNTIME_DIR=/tmp/runtime-root \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  -v "$WORKSPACE_DIR":/root/ws_moveit \
  -v "$HOME/.Xauthority":/root/.Xauthority:rw \
  "${camera_devices[@]}" \
  -v "$TEMP_ENTRYPOINT":/entrypoint.sh:ro \
  --entrypoint /entrypoint.sh \
  "$IMAGE_NAME" \
  bash

# ================================================================
# Revoke X11
# ================================================================
echo "🔒 Revoking X11 local Docker connections..."
xhost -local:docker
echo "🛑 Container session ended."