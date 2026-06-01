import os
import tempfile

import yaml
from jinja2 import Environment, FileSystemLoader
from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('sim',         default_value='true',
                              description='Run in simulation (true) or with real hardware (false).'),
        DeclareLaunchArgument('rviz',        default_value='true',
                              description='Launch RViz2 for visualization.'),
        DeclareLaunchArgument('rsp',         default_value='true',
                              description='Launch robot_state_publisher. Set false if the parent system already runs it.'),
        DeclareLaunchArgument('use_noise',   default_value='',
                              description='Enable sensor noise: true|false. Empty reads sensor_params.yaml.'),
        DeclareLaunchArgument('use_gpu',     default_value='true',
                              description='Use gpu_lidar (true) or cpu lidar (false). Simulation only.'),
        DeclareLaunchArgument('prefix',      default_value='',
                              description='Name prefix for all links and joints.'),
        DeclareLaunchArgument('namespace',   default_value='',
                              description='ROS 2 namespace for the scan topic.'),
        DeclareLaunchArgument('parent_link', default_value='map',
                              description='Parent link the sensor joint attaches to.'),
        DeclareLaunchArgument('x',     default_value='0.0', description='X offset (m).'),
        DeclareLaunchArgument('y',     default_value='0.0', description='Y offset (m).'),
        DeclareLaunchArgument('z',     default_value='0.0', description='Z offset (m).'),
        DeclareLaunchArgument('roll',  default_value='0.0', description='Roll (rad).'),
        DeclareLaunchArgument('pitch', default_value='0.0', description='Pitch (rad).'),
        DeclareLaunchArgument('yaw',   default_value='0.0', description='Yaw (rad).'),
        OpaqueFunction(function=_launch),
    ])


def _launch(context, *args, **kwargs):
    lc = context.launch_configurations

    sim         = lc['sim'].lower() == 'true'
    use_rviz    = lc['rviz'].lower() == 'true'
    use_rsp     = lc['rsp'].lower() == 'true'
    noise_arg   = lc['use_noise']
    use_gpu     = lc['use_gpu'].lower() == 'true'
    prefix      = lc['prefix']
    namespace   = lc['namespace']
    parent_link = lc['parent_link']
    x           = float(lc['x'])
    y           = float(lc['y'])
    z           = float(lc['z'])
    roll        = float(lc['roll'])
    pitch       = float(lc['pitch'])
    yaw         = float(lc['yaw'])

    pkg_share    = get_package_share_directory('caddy_ai2_ros2_sensors_ydlidar_x4')
    gz_sim_share = get_package_share_directory('ros_gz_sim')

    with open(os.path.join(pkg_share, 'bringup', 'config', 'sensor_params.yaml')) as f:
        params = yaml.safe_load(f)

    si = params['simulation']
    op = params['operation']
    no = si['noise']
    noise_enabled = no['enabled'] if noise_arg == '' else noise_arg.lower() == 'true'

    desc_env = Environment(
        loader=FileSystemLoader(os.path.join(pkg_share, 'description')),
        keep_trailing_newline=True,
    )

    base = dict(
        prefix=prefix, parent_link=parent_link,
        x=x, y=y, z=z, roll=roll, pitch=pitch, yaw=yaw,
        mesh_uri='',
    )
    sensor = dict(
        **base,
        namespace=namespace,
        angle_min=si['angle_min'], angle_max=si['angle_max'],
        range_min=si['range_min'], range_max=si['range_max'],
        resolution=op['resolution'], frequency=op['frequency'],
        use_gpu=use_gpu,
        noise_enabled=noise_enabled,
        noise_mean=no['mean'], noise_stddev=no['stddev'],
    )

    rsp_sdf = desc_env.get_template('world.sdf.j2').render(
        **base, model_only=True, with_sensor=False
    )

    nodes = []
    scan_topic = f'/{namespace}/ydlidar_x4/scan' if namespace else '/ydlidar_x4/scan'

    if sim:
        world_str = desc_env.get_template('world.sdf.j2').render(
            **sensor, gui=True, with_sensor=True
        )
        tmp_world = tempfile.NamedTemporaryFile(
            mode='w', suffix='.sdf', prefix='ydlidar_world_', delete=False
        )
        tmp_world.write(world_str)
        tmp_world.close()

        nodes += [
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(gz_sim_share, 'launch', 'gz_sim.launch.py')
                ),
                launch_arguments=[('gz_args', f'-r {tmp_world.name} -v 3')],
            ),
            Node(
                package='ros_gz_bridge',
                executable='parameter_bridge',
                arguments=[
                    '/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock',
                    f'{scan_topic}@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan',
                ],
                output='screen',
            ),
        ] + ([
            Node(
                package='robot_state_publisher',
                executable='robot_state_publisher',
                output='screen',
                parameters=[{'robot_description': rsp_sdf, 'use_sim_time': True}],
            ),
        ] if use_rsp else [])
    else:
        cfg_env = Environment(
            loader=FileSystemLoader(os.path.join(pkg_share, 'bringup', 'config')),
            keep_trailing_newline=True,
        )
        node_params_str = cfg_env.get_template('ydlidar_x4_node_params.yaml.j2').render(**op)
        tmp_cfg = tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', prefix='ydlidar_x4_params_', delete=False
        )
        tmp_cfg.write(node_params_str)
        tmp_cfg.close()

        nodes += [
            Node(
                package='caddy_ai2_ros2_sensors_ydlidar_x4',
                executable='ydlidar_node',
                name='ydlidar_node',
                output='screen',
                parameters=[tmp_cfg.name],
                namespace='ydlidar_x4' if not namespace else namespace,
                remappings=[('scan', 'scan')],
            ),
        ] + ([
            Node(
                package='robot_state_publisher',
                executable='robot_state_publisher',
                output='screen',
                parameters=[{'robot_description': rsp_sdf}],
            ),
        ] if use_rsp else [])

    if use_rviz:
        rviz_cfg = os.path.join(pkg_share, 'bringup', 'rviz', 'ydlidar_x4.rviz')
        nodes.append(Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            output='log',
            arguments=['-d', rviz_cfg],
        ))

    return nodes
