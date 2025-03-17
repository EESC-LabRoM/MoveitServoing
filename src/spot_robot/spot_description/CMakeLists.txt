cmake_minimum_required(VERSION 3.0.2)
project(spot_description)

find_package(catkin REQUIRED COMPONENTS
  xacro
  gazebo_ros
)

catkin_package()

install(
  DIRECTORY urdf/
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/urdf
)

install(
  DIRECTORY meshes/
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/meshes
)

install(
  DIRECTORY launch/
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/launch
)
