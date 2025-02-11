# MoveitServoing

This is the main repository for running the movit servoing packager for the real-time control of robotic arms.

The current version is working for a UR5 robot. I'm using a ros noetic docker.

'pose_tracking_servo.cpp' looks for target_pose and moves to it.

'pose_tracking_settings.yaml' is the configuration file for the pids.

'ur_simulated_config.yaml' is the configuration file for a UR5 (we will use the spot but we have it just for reference).

'pose_tracking.launch' is the launch file.

## How to setup the workspace
1. Download the docker project available at:  [Google Drive](https://drive.google.com/file/d/15ymq-2cHyd-nZnVOon3Vma5lJJu2II5L/view?usp=drive_link)
2. You will need to have a catkin workspace setup:
```
mkdir -p ~/ws_moveit/src

cd ~/ws_moveit/
```
3. Clone and place the files from this rep inside your workspace.
4. Load the docker project by running:
```
docker load -i my-docker-project.tar
```
5. Re-build and re-source the workspace.
```
cd ~/ws_moveit/

catkin build

source devel/setup.bash
```
6. Launch the Gazebo simulation:
```
roscore

roslaunch ur_gazebo ur5.launch

roslaunch ur5_moveit_config ur5_moveit_planning_execution.launch sim:=true

roslaunch ur5_moveit_config moveit_rviz.launch config:=true
```
7. In RViz, grab the red/blue/green "interactive marker" and drag the robot to a non-singular position (not all zero joint angles) that is not close to a joint limit. Click "plan and execute" to move the robot to that pose.

8. Switch to a compatible type of ros-control controller. It should be a JointGroupVelocityController or a JointGroupPositionController, not a trajectory controller like MoveIt usually requires.
```
stop_controllers: ['arm_controller']
strictness: 0
start_asap: false
timeout: 0.0"
```
9. Launch the servo node.
```
roslaunch moveit_servo pose_tracking_servo.launch
```
10. You can publish example servo commands from the command line with:
```
rosrun tf2_ros static_transform_publisher 0.2 0 1.0 0 0 0 1 base_link ee_target
```


This tf will eventually break the simulation, but at least you can use it for testing the code.

You can visualize the tf using RViz if you go to Add > TF. You can hide all the other tfs except for ee_target, as only this one matters for now.


## Next steps:
1. Replace the ur5 with the spot robot. We need to remember to change all the pertinent configs for moveit and gazebo.
2. Make sure that the frames under '## Other frames' are both at the frame of the end-effector (that you want to move to target pose)

   
