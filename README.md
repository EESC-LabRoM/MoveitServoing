
---

# MoveIt ROS1 Workspace Setup

This document provides instructions for setting up the MoveIt ROS1 workspace using Docker, which includes RealSense camera support, Intel MediaPipe, and Boston Dynamics Spot SDK.

## Prerequisites

* Docker installed on your system
* X11 display server for GUI applications
* USB camera (optional, for computer vision applications)

## Cloning the Workspace (Recommended Method)

To get started, clone this repository and all its necessary submodules (like MoveIt, RealSense drivers, etc.) in one go. This is an efficient way to ensure you have all the code components from the get-go.

Open your terminal and run:

```bash
git clone -b spot_teleop --recurse-submodules https://github.com/EESC-LabRoM/MoveitServoing.git ws_moveit
```

**What this command does:**

* `git clone`: The standard command to copy a repository.
* `-b spot_teleop`: This flag ensures you are cloning the `spot_teleop` branch, which contains the latest stable and functional code for this project.
* `--recurse-submodules`: This is the key part! It automatically initializes and clones all the submodules defined in the repository (e.g., `moveit`, `realsense-ros`, `ddynamic_reconfigure`) into their respective `src/` subdirectories.
* `https://github.com/EESC-LabRoM/MoveitServoing.git`: This is the URL of the main repository.
* `ws_moveit`: This will be the name of the directory created on your local machine containing the entire workspace.

After cloning, you can proceed to the Docker setup.

## Setup Instructions

### 1. Building the Docker Image

The first step is to build the Docker image from the provided `Dockerfile`. Navigate into the cloned `ws_moveit` directory if you're not already there:

```bash
cd ws_moveit # If you cloned into a directory named ws_moveit
docker build -t moveit_ros1:latest .
```

This command builds a Docker image tagged as `moveit_ros1:latest` using the `Dockerfile` in the current directory. The process may take several minutes as it:

* Uses the `ROS Noetic desktop-full` image as base.
* Installs necessary dependencies for MoveIt, RealSense, and computer vision.
* Builds and installs `librealsense` from source.
* Installs various ROS packages including MoveIt, Gazebo, and visualization tools.
* Sets up Python dependencies including MediaPipe and Boston Dynamics Spot SDK.
* Creates a pre-configured ROS workspace.

### 2. Setting Up and Running the Container

After successfully building the Docker image, you need to make the `run.sh` script executable and then launch the container:

```bash
# Make the run script executable
chmod +x ./run.sh

# Launch the Docker container
./run.sh
```

The `run.sh` script performs the following actions:

* Grants X11 access for GUI applications.
* Detects available camera devices and mounts them in the container.
* Creates a temporary entrypoint script that configures the environment.
* Mounts the host workspace directory to the container.
* Starts the container with proper privileges and network settings.
* Revokes X11 access after the session ends.

## Workspace Structure

The ROS workspace is mounted at `/root/ws_moveit` within the container and is synchronized with the `~/ws_moveit` directory on your host system (or wherever you cloned it). Any changes made inside the container will persist in your host directory.

### Directory Structure

```
ws_moveit/
├── src/
│   ├── arm_pose_estimator/       # Wrist tracking with ArUco and MediaPipe
│   │   ├── launch/               # Launch files for the system
│   │   │   └── start_arm_pose_estimator.launch
│   │   ├── scripts/              
│   │   │   └── arm_pose_estimator.py  # Main tracking script
│   │   └── ...
│   ├── moveit/                   # MoveIt packages (submodule)
│   ├── realsense-ros/            # RealSense camera ROS drivers (submodule)
│   ├── ddynamic_reconfigure/     # Dynamic reconfigure without cfg (submodule)
│   └── ...                       # Other ROS packages
├── build/                        # Build artifacts
├── devel/                        # Development space
└── install/                      # Install space
```

## Hardware Support

The container is set up with support for:

* Intel RealSense cameras
* Standard USB cameras
* Boston Dynamics Spot SDK for robot interfacing

## Working with the Workspace

Once inside the container, you will likely need to build the workspace if it's the first time or if new packages were added:

```bash
cd /root/ws_moveit
catkin build
source devel/setup.bash
```

Then you can:

* Run RViz using `rosrun rviz rviz`.
* Launch MoveIt tools and demonstrations.
* Develop and test computer vision applications using MediaPipe.
* Control Spot robot using the Boston Dynamics Spot SDK.

> **IMPORTANT:** When opening a new terminal in the container, always source the ROS workspace first:
> `source /root/ws_moveit/devel/setup.bash`
> This ensures that ROS can find all packages and executables in your workspace. Without this step, commands will fail with "package not found" or similar errors.

### 3. Running the Arm Pose Estimator

After entering the container and building/sourcing the workspace, launch the arm pose estimator which uses a RealSense camera, ArUco markers for calibration, and MediaPipe for wrist tracking:

```bash
roslaunch arm_pose_estimator start_arm_pose_estimator.launch
```

This launch file performs several key operations:

* Starts the RealSense camera node with optimized configuration.
* Ensures camera streams are aligned and properly configured.
* Launches the arm pose estimator node with a brief delay to ensure camera initialization.
* Enables visualization for debugging.
* Configures the ArUco marker size (default: 0.2 meters).

The arm pose estimator will:

1.  First detect an ArUco marker to establish a reference frame.
2.  Track the user's wrist position using MediaPipe.
3.  Convert 2D detections to 3D space using depth data.
4.  Publish the wrist position as a TF transform that can be used by MoveIt.

Position yourself in front of the camera with the ArUco marker visible (typically placed on your chest) to complete the calibration process.

### 4. Launching the Spot Robot Simulation

Once the arm pose estimator is running and publishing the wrist TF transform, open a new terminal in the container (remember to source `/root/ws_moveit/devel/setup.bash`) and launch the Spot robot simulation:

```bash
roslaunch spot_moveit_config demo.launch
```

This launch file will:

* Load the Spot robot model with its manipulator.
* Launch RViz with the MoveIt configuration.
* Provide an interactive marker that allows controlling the manipulator's position.
* Connect the wrist tracking from the previous step to allow control through body movements.

### 5. Configuring RViz and Controlling the Manipulator

After launching the simulation, you need to configure RViz for proper robot control:

1.  In the RViz interface, locate the **"Planned Path"** section in the left panel.
2.  Disable the **"Loop Animation"** option by unchecking the box.
3.  In the **"Manipulator Group"** section, change the selection from **"End Effector"** to **"Manipulator"**.
4.  Use the interactive marker (colored arrows and rings) to move the manipulator to a valid position.
5.  Click the **"Plan and Execute"** button to make the robot move to the desired position.

The robot will now plan a trajectory and execute the movement in the Gazebo simulation. You can repeat this process to explore different robot positions and movements.

### 6. Controlling the Physical Spot Robot

To transfer the simulated arm movements to the physical Spot robot, run the following script:

```bash
rosrun spot_operation continuous_direct_grasp.py
```

This script performs the following functions:

* Reads the current end-effector pose from the Gazebo simulation.
* Connects to the physical Spot robot using the Boston Dynamics SDK.
* Transforms the simulated pose to the appropriate reference frame.
* Continuously sends pose commands to the physical robot's arm.
* Updates at 2Hz to ensure smooth motion.

**Important Requirements:**

* The Spot robot must **not** be docked.
* Your computer must be connected to the Spot robot's WiFi network.
* Default IP address is `192.168.80.3` (configurable via ROS parameters).
* Authentication is required (default credentials are used in the script).
* The physical Spot robot must have an arm attachment.

If everything is configured correctly, the physical robot should mirror the same pose as shown in the simulation environment.

## Additional Information

The container automatically detects new packages in the workspace and rebuilds them as necessary. The workspace is configured with:

* Release build type for optimal performance.
* Full ROS Noetic desktop environment.
* MoveIt configuration for robot manipulation.
* Vision processing tools for camera integration.

For more details on the container configuration, refer to the `Dockerfile`.

---
