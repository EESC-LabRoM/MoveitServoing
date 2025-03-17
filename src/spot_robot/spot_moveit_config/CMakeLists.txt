cmake_minimum_required(VERSION 3.0.2)
project(spot_moveit_config)

find_package(catkin REQUIRED COMPONENTS
  moveit_ros_planning_interface
  moveit_ros_move_group
  moveit_kinematics
  moveit_simple_controller_manager
  joint_state_publisher
  joint_state_publisher_gui
  tf
  xacro
  controller_manager
  moveit_ros_visualization
  moveit_ros_warehouse
  moveit_setup_assistant
  robot_state_publisher
  rviz
  spot_description
)

catkin_package()

install(DIRECTORY launch DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION})
install(DIRECTORY config DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION})
install(FILES .setup_assistant DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION})
