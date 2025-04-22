#!/bin/bash

# Set display to match the host
export DISPLAY=:1

# Source environment
source /opt/ros/noetic/setup.bash
if [ -f "/root/ws_moveit/devel/setup.bash" ]; then
  source /root/ws_moveit/devel/setup.bash
fi

# Fix potential Qt/X11 issues for RViz and other GUI applications
export QT_X11_NO_MITSHM=1
export XDG_RUNTIME_DIR=/tmp/runtime-root

# Only rebuild if explicitly needed
if [ "$1" = "--rebuild" ]; then
  echo "Rebuilding workspace..."
  cd /root/ws_moveit
  catkin build
  source /root/ws_moveit/devel/setup.bash
  shift
fi

# Execute whatever command was passed
exec "$@"
