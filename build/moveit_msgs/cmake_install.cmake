# Install script for directory: /root/ws_moveit/src/moveit_msgs

# Set the install prefix
if(NOT DEFINED CMAKE_INSTALL_PREFIX)
  set(CMAKE_INSTALL_PREFIX "/root/ws_moveit/install")
endif()
string(REGEX REPLACE "/$" "" CMAKE_INSTALL_PREFIX "${CMAKE_INSTALL_PREFIX}")

# Set the install configuration name.
if(NOT DEFINED CMAKE_INSTALL_CONFIG_NAME)
  if(BUILD_TYPE)
    string(REGEX REPLACE "^[^A-Za-z0-9_]+" ""
           CMAKE_INSTALL_CONFIG_NAME "${BUILD_TYPE}")
  else()
    set(CMAKE_INSTALL_CONFIG_NAME "Release")
  endif()
  message(STATUS "Install configuration: \"${CMAKE_INSTALL_CONFIG_NAME}\"")
endif()

# Set the component getting installed.
if(NOT CMAKE_INSTALL_COMPONENT)
  if(COMPONENT)
    message(STATUS "Install component: \"${COMPONENT}\"")
    set(CMAKE_INSTALL_COMPONENT "${COMPONENT}")
  else()
    set(CMAKE_INSTALL_COMPONENT)
  endif()
endif()

# Install shared libraries without execute permission?
if(NOT DEFINED CMAKE_INSTALL_SO_NO_EXE)
  set(CMAKE_INSTALL_SO_NO_EXE "1")
endif()

# Is this installation the result of a crosscompile?
if(NOT DEFINED CMAKE_CROSSCOMPILING)
  set(CMAKE_CROSSCOMPILING "FALSE")
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  
      if (NOT EXISTS "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}")
        file(MAKE_DIRECTORY "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}")
      endif()
      if (NOT EXISTS "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/.catkin")
        file(WRITE "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/.catkin" "")
      endif()
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  list(APPEND CMAKE_ABSOLUTE_DESTINATION_FILES
   "/root/ws_moveit/install/_setup_util.py")
  if(CMAKE_WARN_ON_ABSOLUTE_INSTALL_DESTINATION)
    message(WARNING "ABSOLUTE path INSTALL DESTINATION : ${CMAKE_ABSOLUTE_DESTINATION_FILES}")
  endif()
  if(CMAKE_ERROR_ON_ABSOLUTE_INSTALL_DESTINATION)
    message(FATAL_ERROR "ABSOLUTE path INSTALL DESTINATION forbidden (by caller): ${CMAKE_ABSOLUTE_DESTINATION_FILES}")
  endif()
file(INSTALL DESTINATION "/root/ws_moveit/install" TYPE PROGRAM FILES "/root/ws_moveit/build/moveit_msgs/catkin_generated/installspace/_setup_util.py")
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  list(APPEND CMAKE_ABSOLUTE_DESTINATION_FILES
   "/root/ws_moveit/install/env.sh")
  if(CMAKE_WARN_ON_ABSOLUTE_INSTALL_DESTINATION)
    message(WARNING "ABSOLUTE path INSTALL DESTINATION : ${CMAKE_ABSOLUTE_DESTINATION_FILES}")
  endif()
  if(CMAKE_ERROR_ON_ABSOLUTE_INSTALL_DESTINATION)
    message(FATAL_ERROR "ABSOLUTE path INSTALL DESTINATION forbidden (by caller): ${CMAKE_ABSOLUTE_DESTINATION_FILES}")
  endif()
file(INSTALL DESTINATION "/root/ws_moveit/install" TYPE PROGRAM FILES "/root/ws_moveit/build/moveit_msgs/catkin_generated/installspace/env.sh")
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  list(APPEND CMAKE_ABSOLUTE_DESTINATION_FILES
   "/root/ws_moveit/install/setup.bash;/root/ws_moveit/install/local_setup.bash")
  if(CMAKE_WARN_ON_ABSOLUTE_INSTALL_DESTINATION)
    message(WARNING "ABSOLUTE path INSTALL DESTINATION : ${CMAKE_ABSOLUTE_DESTINATION_FILES}")
  endif()
  if(CMAKE_ERROR_ON_ABSOLUTE_INSTALL_DESTINATION)
    message(FATAL_ERROR "ABSOLUTE path INSTALL DESTINATION forbidden (by caller): ${CMAKE_ABSOLUTE_DESTINATION_FILES}")
  endif()
file(INSTALL DESTINATION "/root/ws_moveit/install" TYPE FILE FILES
    "/root/ws_moveit/build/moveit_msgs/catkin_generated/installspace/setup.bash"
    "/root/ws_moveit/build/moveit_msgs/catkin_generated/installspace/local_setup.bash"
    )
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  list(APPEND CMAKE_ABSOLUTE_DESTINATION_FILES
   "/root/ws_moveit/install/setup.sh;/root/ws_moveit/install/local_setup.sh")
  if(CMAKE_WARN_ON_ABSOLUTE_INSTALL_DESTINATION)
    message(WARNING "ABSOLUTE path INSTALL DESTINATION : ${CMAKE_ABSOLUTE_DESTINATION_FILES}")
  endif()
  if(CMAKE_ERROR_ON_ABSOLUTE_INSTALL_DESTINATION)
    message(FATAL_ERROR "ABSOLUTE path INSTALL DESTINATION forbidden (by caller): ${CMAKE_ABSOLUTE_DESTINATION_FILES}")
  endif()
file(INSTALL DESTINATION "/root/ws_moveit/install" TYPE FILE FILES
    "/root/ws_moveit/build/moveit_msgs/catkin_generated/installspace/setup.sh"
    "/root/ws_moveit/build/moveit_msgs/catkin_generated/installspace/local_setup.sh"
    )
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  list(APPEND CMAKE_ABSOLUTE_DESTINATION_FILES
   "/root/ws_moveit/install/setup.zsh;/root/ws_moveit/install/local_setup.zsh")
  if(CMAKE_WARN_ON_ABSOLUTE_INSTALL_DESTINATION)
    message(WARNING "ABSOLUTE path INSTALL DESTINATION : ${CMAKE_ABSOLUTE_DESTINATION_FILES}")
  endif()
  if(CMAKE_ERROR_ON_ABSOLUTE_INSTALL_DESTINATION)
    message(FATAL_ERROR "ABSOLUTE path INSTALL DESTINATION forbidden (by caller): ${CMAKE_ABSOLUTE_DESTINATION_FILES}")
  endif()
file(INSTALL DESTINATION "/root/ws_moveit/install" TYPE FILE FILES
    "/root/ws_moveit/build/moveit_msgs/catkin_generated/installspace/setup.zsh"
    "/root/ws_moveit/build/moveit_msgs/catkin_generated/installspace/local_setup.zsh"
    )
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  list(APPEND CMAKE_ABSOLUTE_DESTINATION_FILES
   "/root/ws_moveit/install/.rosinstall")
  if(CMAKE_WARN_ON_ABSOLUTE_INSTALL_DESTINATION)
    message(WARNING "ABSOLUTE path INSTALL DESTINATION : ${CMAKE_ABSOLUTE_DESTINATION_FILES}")
  endif()
  if(CMAKE_ERROR_ON_ABSOLUTE_INSTALL_DESTINATION)
    message(FATAL_ERROR "ABSOLUTE path INSTALL DESTINATION forbidden (by caller): ${CMAKE_ABSOLUTE_DESTINATION_FILES}")
  endif()
file(INSTALL DESTINATION "/root/ws_moveit/install" TYPE FILE FILES "/root/ws_moveit/build/moveit_msgs/catkin_generated/installspace/.rosinstall")
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/share/moveit_msgs/action" TYPE FILE FILES
    "/root/ws_moveit/src/moveit_msgs/action/ExecuteTrajectory.action"
    "/root/ws_moveit/src/moveit_msgs/action/MoveGroup.action"
    "/root/ws_moveit/src/moveit_msgs/action/MoveGroupSequence.action"
    "/root/ws_moveit/src/moveit_msgs/action/Pickup.action"
    "/root/ws_moveit/src/moveit_msgs/action/Place.action"
    )
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/share/moveit_msgs/msg" TYPE FILE FILES
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/ExecuteTrajectoryAction.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/ExecuteTrajectoryActionGoal.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/ExecuteTrajectoryActionResult.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/ExecuteTrajectoryActionFeedback.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/ExecuteTrajectoryGoal.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/ExecuteTrajectoryResult.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/ExecuteTrajectoryFeedback.msg"
    )
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/share/moveit_msgs/msg" TYPE FILE FILES
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/MoveGroupAction.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/MoveGroupActionGoal.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/MoveGroupActionResult.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/MoveGroupActionFeedback.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/MoveGroupGoal.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/MoveGroupResult.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/MoveGroupFeedback.msg"
    )
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/share/moveit_msgs/msg" TYPE FILE FILES
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/MoveGroupSequenceAction.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/MoveGroupSequenceActionGoal.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/MoveGroupSequenceActionResult.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/MoveGroupSequenceActionFeedback.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/MoveGroupSequenceGoal.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/MoveGroupSequenceResult.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/MoveGroupSequenceFeedback.msg"
    )
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/share/moveit_msgs/msg" TYPE FILE FILES
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/PickupAction.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/PickupActionGoal.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/PickupActionResult.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/PickupActionFeedback.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/PickupGoal.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/PickupResult.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/PickupFeedback.msg"
    )
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/share/moveit_msgs/msg" TYPE FILE FILES
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/PlaceAction.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/PlaceActionGoal.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/PlaceActionResult.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/PlaceActionFeedback.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/PlaceGoal.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/PlaceResult.msg"
    "/root/ws_moveit/devel/.private/moveit_msgs/share/moveit_msgs/msg/PlaceFeedback.msg"
    )
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/share/moveit_msgs/msg" TYPE FILE FILES
    "/root/ws_moveit/src/moveit_msgs/msg/AllowedCollisionEntry.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/AllowedCollisionMatrix.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/AttachedCollisionObject.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/BoundingVolume.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/CartesianPoint.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/CartesianTrajectory.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/CartesianTrajectoryPoint.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/CollisionObject.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/ConstraintEvalResult.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/Constraints.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/CostSource.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/ContactInformation.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/DisplayTrajectory.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/DisplayRobotState.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/GenericTrajectory.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/Grasp.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/GripperTranslation.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/JointConstraint.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/JointLimits.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/LinkPadding.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/LinkScale.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/MotionPlanRequest.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/MotionPlanResponse.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/MotionPlanDetailedResponse.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/MotionSequenceItem.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/MotionSequenceRequest.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/MotionSequenceResponse.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/MoveItErrorCodes.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/TrajectoryConstraints.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/ObjectColor.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/OrientationConstraint.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/OrientedBoundingBox.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/PlaceLocation.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/PlannerInterfaceDescription.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/PlannerParams.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/PlanningScene.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/PlanningSceneComponents.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/PlanningSceneWorld.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/PlanningOptions.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/PositionConstraint.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/RobotState.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/RobotTrajectory.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/VisibilityConstraint.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/WorkspaceParameters.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/KinematicSolverInfo.msg"
    "/root/ws_moveit/src/moveit_msgs/msg/PositionIKRequest.msg"
    )
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/share/moveit_msgs/srv" TYPE FILE FILES
    "/root/ws_moveit/src/moveit_msgs/srv/GetMotionPlan.srv"
    "/root/ws_moveit/src/moveit_msgs/srv/ExecuteKnownTrajectory.srv"
    "/root/ws_moveit/src/moveit_msgs/srv/GetStateValidity.srv"
    "/root/ws_moveit/src/moveit_msgs/srv/GetCartesianPath.srv"
    "/root/ws_moveit/src/moveit_msgs/srv/GetPlanningScene.srv"
    "/root/ws_moveit/src/moveit_msgs/srv/GraspPlanning.srv"
    "/root/ws_moveit/src/moveit_msgs/srv/ApplyPlanningScene.srv"
    "/root/ws_moveit/src/moveit_msgs/srv/QueryPlannerInterfaces.srv"
    "/root/ws_moveit/src/moveit_msgs/srv/GetMotionSequence.srv"
    "/root/ws_moveit/src/moveit_msgs/srv/GetPositionFK.srv"
    "/root/ws_moveit/src/moveit_msgs/srv/GetPositionIK.srv"
    "/root/ws_moveit/src/moveit_msgs/srv/GetPlannerParams.srv"
    "/root/ws_moveit/src/moveit_msgs/srv/SetPlannerParams.srv"
    "/root/ws_moveit/src/moveit_msgs/srv/UpdatePointcloudOctomap.srv"
    "/root/ws_moveit/src/moveit_msgs/srv/SaveMap.srv"
    "/root/ws_moveit/src/moveit_msgs/srv/LoadMap.srv"
    "/root/ws_moveit/src/moveit_msgs/srv/SaveRobotStateToWarehouse.srv"
    "/root/ws_moveit/src/moveit_msgs/srv/ListRobotStatesInWarehouse.srv"
    "/root/ws_moveit/src/moveit_msgs/srv/GetRobotStateFromWarehouse.srv"
    "/root/ws_moveit/src/moveit_msgs/srv/CheckIfRobotStateExistsInWarehouse.srv"
    "/root/ws_moveit/src/moveit_msgs/srv/RenameRobotStateInWarehouse.srv"
    "/root/ws_moveit/src/moveit_msgs/srv/DeleteRobotStateFromWarehouse.srv"
    "/root/ws_moveit/src/moveit_msgs/srv/ChangeControlDimensions.srv"
    "/root/ws_moveit/src/moveit_msgs/srv/ChangeDriftDimensions.srv"
    )
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/share/moveit_msgs/cmake" TYPE FILE FILES "/root/ws_moveit/build/moveit_msgs/catkin_generated/installspace/moveit_msgs-msg-paths.cmake")
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/include" TYPE DIRECTORY FILES "/root/ws_moveit/devel/.private/moveit_msgs/include/moveit_msgs")
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/share/roseus/ros" TYPE DIRECTORY FILES "/root/ws_moveit/devel/.private/moveit_msgs/share/roseus/ros/moveit_msgs")
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/share/common-lisp/ros" TYPE DIRECTORY FILES "/root/ws_moveit/devel/.private/moveit_msgs/share/common-lisp/ros/moveit_msgs")
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/share/gennodejs/ros" TYPE DIRECTORY FILES "/root/ws_moveit/devel/.private/moveit_msgs/share/gennodejs/ros/moveit_msgs")
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  execute_process(COMMAND "/usr/bin/python3" -m compileall "/root/ws_moveit/devel/.private/moveit_msgs/lib/python3/dist-packages/moveit_msgs")
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib/python3/dist-packages" TYPE DIRECTORY FILES "/root/ws_moveit/devel/.private/moveit_msgs/lib/python3/dist-packages/moveit_msgs")
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib/pkgconfig" TYPE FILE FILES "/root/ws_moveit/build/moveit_msgs/catkin_generated/installspace/moveit_msgs.pc")
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/share/moveit_msgs/cmake" TYPE FILE FILES "/root/ws_moveit/build/moveit_msgs/catkin_generated/installspace/moveit_msgs-msg-extras.cmake")
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/share/moveit_msgs/cmake" TYPE FILE FILES
    "/root/ws_moveit/build/moveit_msgs/catkin_generated/installspace/moveit_msgsConfig.cmake"
    "/root/ws_moveit/build/moveit_msgs/catkin_generated/installspace/moveit_msgsConfig-version.cmake"
    )
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/share/moveit_msgs" TYPE FILE FILES "/root/ws_moveit/src/moveit_msgs/package.xml")
endif()

if(NOT CMAKE_INSTALL_LOCAL_ONLY)
  # Include the install script for each subdirectory.
  include("/root/ws_moveit/build/moveit_msgs/gtest/cmake_install.cmake")

endif()

if(CMAKE_INSTALL_COMPONENT)
  set(CMAKE_INSTALL_MANIFEST "install_manifest_${CMAKE_INSTALL_COMPONENT}.txt")
else()
  set(CMAKE_INSTALL_MANIFEST "install_manifest.txt")
endif()

string(REPLACE ";" "\n" CMAKE_INSTALL_MANIFEST_CONTENT
       "${CMAKE_INSTALL_MANIFEST_FILES}")
file(WRITE "/root/ws_moveit/build/moveit_msgs/${CMAKE_INSTALL_MANIFEST}"
     "${CMAKE_INSTALL_MANIFEST_CONTENT}")
