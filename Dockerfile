FROM osrf/ros:noetic-desktop-full

# Set non-interactive frontend for apt
ENV DEBIAN_FRONTEND=noninteractive

# Install general dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    python3-opencv \
    git \
    wget \
    unzip \
    build-essential \
    libudev-dev \
    libusb-1.0-0-dev \
    libssl-dev \
    software-properties-common \
    pkg-config \
    libgtk-3-dev \
    libglfw3-dev \
    libgl1-mesa-dev \
    libglu1-mesa-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Add Intel RealSense repository
RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-key F6E65AC044F831AC80A06380C8B3A55A6F3EFCDE || \
    apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-key F6E65AC044F831AC80A06380C8B3A55A6F3EFCDE && \
    add-apt-repository "deb https://librealsense.intel.com/Debian/apt-repo focal main" -y

# Install RealSense libraries
RUN apt-get update && apt-get install -y \
    librealsense2-dkms \
    librealsense2-utils \
    librealsense2-dev \
    librealsense2-dbg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install ROS packages in smaller groups with cleanup after each step
# Group 1: Core TF2 packages
RUN apt-get update && apt-get install -y \
    ros-noetic-tf2 \
    ros-noetic-tf2-ros \
    ros-noetic-tf2-geometry-msgs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Group 2: MoveIt core packages
RUN apt-get update && apt-get install -y \
    ros-noetic-moveit \
    ros-noetic-moveit-ros-perception \
    ros-noetic-moveit-ros-planning \
    ros-noetic-moveit-ros-planning-interface \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Group 3: MoveIt additional packages
RUN apt-get update && apt-get install -y \
    ros-noetic-moveit-ros-visualization \
    ros-noetic-moveit-servo \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Group 4: Gazebo and visualization
RUN apt-get update && apt-get install -y \
    ros-noetic-gazebo-ros \
    ros-noetic-gazebo-ros-control \
    ros-noetic-joint-state-publisher-gui \
    ros-noetic-rqt-robot-steering \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Group 5: Additional dependencies for rviz_visual_tools and other packages
RUN apt-get update && apt-get install -y \
    ros-noetic-graph-msgs \
    ros-noetic-control-msgs \
    ros-noetic-moveit-msgs \
    ros-noetic-geometric-shapes \
    ros-noetic-moveit-visual-tools \
    ros-noetic-eigen-conversions \
    ros-noetic-ddynamic-reconfigure \
    ros-noetic-image-transport \
    ros-noetic-cv-bridge \
    ros-noetic-image-publisher \
    ros-noetic-code-coverage \
    ros-noetic-ros-controllers \
    ros-noetic-joint-trajectory-controller \
    ros-noetic-position-controllers \
    ros-noetic-velocity-controllers \
    ros-noetic-effort-controllers \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Group 6: Remaining packages and build tools
RUN apt-get update && apt-get install -y \
    ros-noetic-urdf-tutorial \
    ros-noetic-xacro \
    ros-noetic-rviz \
    ros-noetic-message-filters \
    ros-noetic-robot-state-publisher \
    ros-noetic-joint-state-publisher \
    ros-noetic-cv-bridge \
    python3-catkin-tools \
    libxcb-xinerama0 \
    qt5-default \
    libqt5x11extras5 \
    libgl1-mesa-glx \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN apt-get update && apt-get install -y \
    python3-tk \
    python3-matplotlib \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-cache-dir \
    mediapipe \
    transforms3d \
    numpy \
    opencv-contrib-python \
    future

# Set up workspace directory
RUN mkdir -p /root/ws_moveit/src

# Run rosdep update once during image build
RUN rosdep update

# Clone RealSense-ROS package
RUN cd /root/ws_moveit/src && \
    git clone https://github.com/IntelRealSense/realsense-ros.git && \
    cd realsense-ros && \
    git checkout `git tag | sort -V | grep -P "^2\\.\d+\\.\\d+" | tail -1`

# Set working directory
WORKDIR /root/ws_moveit

# Install all ROS dependencies during build
RUN apt-get update && \
    rosdep install --from-paths src --ignore-src -r -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Build the workspace with RealSense packages using catkin build
RUN /bin/bash -c "source /opt/ros/noetic/setup.bash && \
    catkin init && \
    catkin config --extend /opt/ros/noetic --cmake-args -DCMAKE_BUILD_TYPE=Release -DCATKIN_ENABLE_TESTING=False && \
    catkin build && \
    catkin build --catkin-make-args install"

# Configure ROS environment
RUN echo "source /opt/ros/noetic/setup.bash" >> ~/.bashrc && \
    echo "source /root/ws_moveit/devel/setup.bash" >> ~/.bashrc

# Create a file to track what has already been processed
RUN touch /root/.workspace_setup_complete

# Improved entrypoint that doesn't install unless needed and handles DISPLAY portability
RUN echo '#!/bin/bash \n\
# Get display from environment or default to :0 \n\
export DISPLAY=${DISPLAY:-:0} \n\
\n\
# Source environment \n\
source /opt/ros/noetic/setup.bash \n\
source /root/ws_moveit/devel/setup.bash \n\
\n\
# Only rebuild if new src files are added and not yet processed \n\
NEED_REBUILD=0 \n\
if [ -d "/root/ws_moveit/src" ]; then \n\
  # Get count of new directories not tracked in last build \n\
  NEW_DIRS=$(find /root/ws_moveit/src -type d -newer /root/.workspace_setup_complete | wc -l) \n\
  if [ "$NEW_DIRS" -gt 0 ]; then \n\
    echo "Detected new packages in workspace. Rebuilding..." \n\
    NEED_REBUILD=1 \n\
  fi \n\
fi \n\
\n\
if [ "$NEED_REBUILD" -eq 1 ]; then \n\
  echo "Installing new dependencies and rebuilding workspace..." \n\
  # Update dependencies with rosdep \n\
  apt-get update \n\
  rosdep install --from-paths src --ignore-src -r -y \n\
  # Build the workspace with catkin build \n\
  catkin build --cmake-args -DCMAKE_BUILD_TYPE=Release -DCATKIN_ENABLE_TESTING=False \n\
  catkin build --catkin-make-args install \n\
  # Update the timestamp of the completion file \n\
  touch /root/.workspace_setup_complete \n\
else \n\
  echo "Workspace is up to date. Skipping rebuild." \n\
fi \n\
\n\
exec "$@"' > /entrypoint.sh && \
chmod +x /entrypoint.sh

# Set the entry point
ENTRYPOINT ["/entrypoint.sh"]

# Default command
CMD ["bash"]