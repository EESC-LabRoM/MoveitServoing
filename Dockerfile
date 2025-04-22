FROM moveit/moveit2:main-jazzy-tutorial-source

# Set non-interactive frontend for apt
ENV DEBIAN_FRONTEND=noninteractive

# vim 
# sudo apt install ros-humble-moveit

# Install general dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    vim \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Boston Dynamics Spot SDK
RUN python3 -m pip install --no-cache-dir --upgrade \
    bosdyn-client \
    bosdyn-mission \
    bosdyn-choreography-client \
    bosdyn-orbit

# # Make sure we have the right permissions for the Spot SDK
# RUN echo "# Spot SDK environment setup" >> ~/.bashrc && \
#     echo "export PYTHONPATH=\$PYTHONPATH:/usr/local/lib/python3.8/dist-packages" >> ~/.bashrc

# # Run rosdep update once during image build
# RUN rosdep update

# # Set up workspace directory
# RUN mkdir -p /root/ws_moveit/src

# Default command
CMD ["bash"]