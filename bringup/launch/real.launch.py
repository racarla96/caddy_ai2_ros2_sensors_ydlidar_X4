import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    """Thin wrapper used by robot.launch.py to auto-include the ydlidar_x4 driver."""
    pkg_share = get_package_share_directory('caddy_ai2_ros2_sensors_ydlidar_x4')
    return LaunchDescription([
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(pkg_share, 'bringup', 'launch', 'general.launch.py')
            ),
            launch_arguments={
                'sim':  'false',
                'rviz': 'false',
                'rsp':  'false',
            }.items(),
        ),
    ])
