###############################################################################
#  🟢  BASE COM ZED SDK + CUDA
###############################################################################
ARG UBUNTU_RELEASE_YEAR=20
ARG ZED_SDK_MAJOR=4
ARG ZED_SDK_MINOR=1
ARG CUDA_MAJOR=11
ARG CUDA_MINOR=4

FROM stereolabs/zed:${ZED_SDK_MAJOR}.${ZED_SDK_MINOR}-gl-devel-cuda${CUDA_MAJOR}.${CUDA_MINOR}-ubuntu${UBUNTU_RELEASE_YEAR}.04

###############################################################################
#  🟡  ROS NOETIC DESKTOP-FULL (repositório oficial)
###############################################################################
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# 1) Ferramentas básicas + chaves GPG
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl gnupg lsb-release && \
    curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
        | apt-key add - && \
    echo "deb http://packages.ros.org/ros/ubuntu $(lsb_release -sc) main" \
        > /etc/apt/sources.list.d/ros-latest.list

# 2) ROS desktop-full + tooling python (rosdep etc.)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ros-noetic-desktop-full \
        python3-pip python3-dev python3-tk python3-matplotlib \
        python3-rosdep python3-rosinstall \
        python3-rosinstall-generator python3-wstool \
        python3-catkin-tools && \
    rosdep init && rosdep update && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

###############################################################################
#  🔵  *** SEU DOCKERFILE ORIGINAL A PARTIR DAQUI ***  (quase intacto)
###############################################################################

# Install general dependencies (mantive sem o python3-opencv!)
RUN apt-get update && apt-get install -y \
    git wget unzip build-essential cmake \
    libudev-dev libusb-1.0-0-dev libssl-dev \
    software-properties-common pkg-config \
    libgtk-3-dev libglfw3-dev libgl1-mesa-dev libglu1-mesa-dev \
    python3-catkin-tools \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Build and install librealsense from source
RUN cd /tmp && \
    git clone https://github.com/IntelRealSense/librealsense.git && \
    cd librealsense && mkdir build && cd build && \
    cmake .. -DCMAKE_BUILD_TYPE=Release \
             -DBUILD_EXAMPLES=false \
             -DBUILD_GRAPHICAL_EXAMPLES=false \
             -DBUILD_WITH_CUDA=false \
             -DBUILD_PYTHON_BINDINGS=false \
             -DBUILD_WITH_TM2=false \
             -DBUILD_UNIT_TESTS=false \
             -DBUILD_WITH_OPENMP=false && \
    make -j$(nproc) && make install && ldconfig && \
    cd / && rm -rf /tmp/librealsense

# ------------------- ROS packages em grupos (igual antes) --------------------

# Core TF2
RUN apt-get update && apt-get install -y \
    ros-noetic-tf2 ros-noetic-tf2-ros ros-noetic-tf2-geometry-msgs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# MoveIt core
RUN apt-get update && apt-get install -y \
    ros-noetic-moveit ros-noetic-moveit-ros-perception \
    ros-noetic-moveit-ros-planning ros-noetic-moveit-ros-planning-interface && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# MoveIt extra
RUN apt-get update && apt-get install -y \
    ros-noetic-moveit-ros-visualization ros-noetic-moveit-servo && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Gazebo / Viz + Octomap
RUN apt-get update && apt-get install -y \
    ros-noetic-gazebo-ros ros-noetic-gazebo-ros-control \
    ros-noetic-octomap-server ros-noetic-octomap-mapping \
    ros-noetic-joint-state-publisher-gui ros-noetic-rqt-robot-steering && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# rviz_visual_tools e cia
RUN apt-get update && apt-get install -y \
    ros-noetic-graph-msgs ros-noetic-control-msgs \
    ros-noetic-moveit-msgs ros-noetic-geometric-shapes \
    ros-noetic-moveit-visual-tools ros-noetic-eigen-conversions \
    ros-noetic-ddynamic-reconfigure ros-noetic-image-transport \
    ros-noetic-cv-bridge ros-noetic-image-publisher \
    ros-noetic-code-coverage \
    ros-noetic-ros-controllers \
    ros-noetic-joint-trajectory-controller \
    ros-noetic-position-controllers \
    ros-noetic-velocity-controllers \
    ros-noetic-effort-controllers && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Pacotes restantes
RUN apt-get update && apt-get install -y \
    ros-noetic-urdf-tutorial ros-noetic-xacro ros-noetic-rviz \
    ros-noetic-message-filters ros-noetic-robot-state-publisher \
    ros-noetic-joint-state-publisher && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# ------------------- Python deps (pandas, ultralytics, OpenCV fix) -----------
RUN pip3 install --no-cache-dir \
    pandas ultralytics mediapipe transforms3d numpy \
    opencv-contrib-python==4.5.3.56 future

# ------------------- Boston Dynamics Spot SDK --------------------------------
RUN python3 -m pip install --no-cache-dir --upgrade \
    bosdyn-client bosdyn-mission bosdyn-choreography-client bosdyn-orbit

# Spot SDK env
RUN echo "# Spot SDK environment setup" >> ~/.bashrc && \
    echo "export PYTHONPATH=\$PYTHONPATH:/usr/local/lib/python3.8/dist-packages" >> ~/.bashrc


# rosdep update (uma vez)
RUN rosdep update

# Workspace setup
RUN mkdir -p /root/ws_moveit/src


WORKDIR /root/ws_moveit

# Dependências do workspace
RUN apt-get update && \
    rosdep install --from-paths src --ignore-src -r -y && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Build do catkin
RUN /bin/bash -c "source /opt/ros/noetic/setup.bash && \
    catkin init && \
    catkin config --extend /opt/ros/noetic && \
    catkin config --cmake-args -DCMAKE_BUILD_TYPE=Release && \
    catkin config --install && \
    catkin build"

# ROS env nos logins futuros
RUN echo "source /opt/ros/noetic/setup.bash" >> ~/.bashrc && \
    echo 'if [ -f "/root/ws_moveit/install/setup.bash" ]; then' >> ~/.bashrc && \
    echo '  source /root/ws_moveit/install/setup.bash' >> ~/.bashrc && \
    echo 'else' >> ~/.bashrc && \
    echo '  source /root/ws_moveit/devel/setup.bash' >> ~/.bashrc && \
    echo 'fi' >> ~/.bashrc

# Timestamp do workspace
RUN touch /root/.workspace_setup_complete

# Entrypoint que recompila só quando detecta coisa nova
RUN echo '#!/bin/bash \n\
export DISPLAY=${DISPLAY:-:0} \n\
source /opt/ros/noetic/setup.bash \n\
if [ -f /root/ws_moveit/install/setup.bash ]; then source /root/ws_moveit/install/setup.bash; else source /root/ws_moveit/devel/setup.bash; fi \n\
NEED_REBUILD=0 \n\
if [ -d /root/ws_moveit/src ]; then NEW_DIRS=$(find /root/ws_moveit/src -type d -newer /root/.workspace_setup_complete | wc -l); [ "$NEW_DIRS" -gt 0 ] && NEED_REBUILD=1; fi \n\
if [ "$NEED_REBUILD" -eq 1 ]; then \n\
  echo \"Detected new packages – rebuilding...\"; \
  apt-get update && rosdep install --from-paths src --ignore-src -r -y && catkin build && touch /root/.workspace_setup_complete; \
else echo \"Workspace up-to-date.\"; fi \n\
exec \"$@\"' > /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]