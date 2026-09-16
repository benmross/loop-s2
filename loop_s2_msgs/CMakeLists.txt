cmake_minimum_required(VERSION 3.8)
project(loop_s2_msgs)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  msg/MissionLeg.msg
  msg/MissionState.msg
  msg/RoverTelemetry.msg
  msg/OperatorCommand.msg
  msg/CommandAck.msg
  DEPENDENCIES std_msgs
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
