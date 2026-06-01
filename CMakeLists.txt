cmake_minimum_required(VERSION 3.5)

project(caddy_ai2_ros2_sensors_ydlidar_x4)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 14)
endif()
if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rmw REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(visualization_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)

set(SDK_PATH "./sdk/")

FILE(GLOB SDK_SRC
  "${SDK_PATH}/src/impl/unix/*.cpp"
  "${SDK_PATH}/src/*.cpp"
  "${SDK_PATH}/src/*.c"
)

include_directories(
  ${PROJECT_SOURCE_DIR}/code/src
  ${PROJECT_SOURCE_DIR}/sdk/include
  ${PROJECT_SOURCE_DIR}/sdk/src
)

add_executable(ydlidar_node code/src/ydlidar_node.cpp ${SDK_SRC})
ament_target_dependencies(ydlidar_node
  "rclcpp"
  "sensor_msgs"
  "visualization_msgs"
  "geometry_msgs"
)

add_executable(ydlidar_client code/src/ydlidar_client.cpp)
ament_target_dependencies(ydlidar_client
  "rclcpp"
  "sensor_msgs"
  "visualization_msgs"
  "geometry_msgs"
)

install(TARGETS
  ydlidar_node ydlidar_client
  DESTINATION lib/${PROJECT_NAME})

install(DIRECTORY bringup description
  DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
