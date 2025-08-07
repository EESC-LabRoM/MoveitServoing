# Message to signal when a Spot command is sent
Header header
string command_type  # "arm_pose", "gripper_open", "gripper_close", "manipulation_api"
geometry_msgs/Pose target_pose  # Target pose if applicable
bool has_pose  # Whether target_pose is valid
