# CMake generated Testfile for 
# Source directory: /root/ws_moveit/src/universal_robot/ur5_e_moveit_config
# Build directory: /root/ws_moveit/build/ur5_e_moveit_config
# 
# This file includes the relevant testing commands required for 
# testing this directory and lists subdirectories to be tested as well.
add_test(_ctest_ur5_e_moveit_config_roslaunch-check_tests_moveit_planning_execution.xml "/root/ws_moveit/build/ur5_e_moveit_config/catkin_generated/env_cached.sh" "/usr/bin/python3" "/opt/ros/noetic/share/catkin/cmake/test/run_tests.py" "/root/ws_moveit/build/ur5_e_moveit_config/test_results/ur5_e_moveit_config/roslaunch-check_tests_moveit_planning_execution.xml.xml" "--return-code" "/usr/bin/cmake -E make_directory /root/ws_moveit/build/ur5_e_moveit_config/test_results/ur5_e_moveit_config" "/opt/ros/noetic/share/roslaunch/cmake/../scripts/roslaunch-check -o \"/root/ws_moveit/build/ur5_e_moveit_config/test_results/ur5_e_moveit_config/roslaunch-check_tests_moveit_planning_execution.xml.xml\" \"/root/ws_moveit/src/universal_robot/ur5_e_moveit_config/tests/moveit_planning_execution.xml\" ")
set_tests_properties(_ctest_ur5_e_moveit_config_roslaunch-check_tests_moveit_planning_execution.xml PROPERTIES  _BACKTRACE_TRIPLES "/opt/ros/noetic/share/catkin/cmake/test/tests.cmake;160;add_test;/opt/ros/noetic/share/roslaunch/cmake/roslaunch-extras.cmake;66;catkin_run_tests_target;/root/ws_moveit/src/universal_robot/ur5_e_moveit_config/CMakeLists.txt;10;roslaunch_add_file_check;/root/ws_moveit/src/universal_robot/ur5_e_moveit_config/CMakeLists.txt;0;")
subdirs("gtest")
