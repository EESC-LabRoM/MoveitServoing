#!/bin/bash

# Permit X11 access
echo "Allowing X11 access..."
xhost +local:docker

# Container and image names
CONTAINER_NAME="moveit_container"
IMAGE_NAME="moveit_ros1:latest"

# Define the workspace directory
WORKSPACE_DIR="$PWD/src"

# Create workspace directory if it doesn't exist
mkdir -p "$WORKSPACE_DIR"

# Detectar o valor do DISPLAY no host
HOST_DISPLAY=$DISPLAY
echo "Using host display: $HOST_DISPLAY"

# Check for camera devices
echo "Detecting camera devices..."
camera_devices=()
for device in /dev/video*; do
    if [ -e "$device" ]; then
        echo "  Found: $device"
        camera_devices+=(--device="${device}:${device}")
    fi
done

if [ ${#camera_devices[@]} -eq 0 ]; then
    echo "Warning: No camera devices were found!"
fi

# Criar um script temporário para o entrypoint que configurará o DISPLAY correto
TEMP_ENTRYPOINT="$WORKSPACE_DIR/tmp_entrypoint.sh"
cat > "$TEMP_ENTRYPOINT" << EOF
#!/bin/bash

# Set display to match the host
export DISPLAY=$HOST_DISPLAY

# Source environment
source /opt/ros/noetic/setup.bash
if [ -f "/root/ws_moveit/devel/setup.bash" ]; then
  source /root/ws_moveit/devel/setup.bash
fi

# Fix potential Qt/X11 issues for RViz and other GUI applications
export QT_X11_NO_MITSHM=1
export XDG_RUNTIME_DIR=/tmp/runtime-root

# Only rebuild if explicitly needed
if [ "\$1" = "--rebuild" ]; then
  echo "Rebuilding workspace..."
  cd /root/ws_moveit
  catkin build
  source /root/ws_moveit/devel/setup.bash
  shift
fi

# Execute whatever command was passed
exec "\$@"
EOF
chmod +x "$TEMP_ENTRYPOINT"

# Run the container
echo "Starting MoveIt ROS1 container..."
docker run -it --rm \
    --name "$CONTAINER_NAME" \
    --net=host \
    --privileged \
    -e DISPLAY=$HOST_DISPLAY \
    -e QT_X11_NO_MITSHM=1 \
    -e XDG_RUNTIME_DIR=/tmp/runtime-root \
    -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
    -v "$WORKSPACE_DIR":/root/ws_moveit/src \
    -v "$TEMP_ENTRYPOINT":/entrypoint.sh \
    -v /dev:/dev \
    -v ~/.Xauthority:/root/.Xauthority:rw \
    "${camera_devices[@]}" \
    --entrypoint /entrypoint.sh \
    "$IMAGE_NAME" \
    bash

# Revoke X11 access
echo "Revoking X11 access..."
xhost -local:docker
echo "Container session ended."
