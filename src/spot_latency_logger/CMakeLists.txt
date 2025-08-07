cmake_minimum_required(VERSION 3.0.2)
project(spot_latency_logger)

## Find catkin macros and libraries
find_package(catkin REQUIRED COMPONENTS
  std_msgs
  sensor_msgs
  geometry_msgs
  message_generation
  tf2_msgs
  std_srvs
  rospy
)

## Generate messages in the 'msg' folder
add_message_files(
  FILES
  SpotCommand.msg
  SpotFeedback.msg
  YoloDetection.msg
)

## Generate added messages and services with any dependencies listed here
generate_messages(
  DEPENDENCIES
  std_msgs
  geometry_msgs
  sensor_msgs
)

catkin_package(
  CATKIN_DEPENDS 
    std_msgs 
    sensor_msgs 
    geometry_msgs 
    message_runtime
    tf2_msgs
    std_srvs
)

## Specify additional locations of header files
include_directories(
  ${catkin_INCLUDE_DIRS}
)

## Install scripts
catkin_install_python(PROGRAMS
  scripts/latency_logger.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
