"""The console and a rover for it to talk to."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    default_mission = os.path.join(get_package_share_directory('loop_s2_gui'),
                                   'config', 'mission.yaml')
    mission = LaunchConfiguration('mission')
    return LaunchDescription([
        DeclareLaunchArgument('mission', default_value=default_mission),
        DeclareLaunchArgument('rover', default_value='true',
                              description='run the simulated rover as well as the console'),
        DeclareLaunchArgument('dropout_every_s', default_value='75.0',
                              description='force a link dropout this often; 0 disables'),
        DeclareLaunchArgument('dropout_duration_s', default_value='7.0'),
        DeclareLaunchArgument('max_speed', default_value='1.2'),

        Node(package='loop_s2_gui', executable='rover_sim', output='screen',
             condition=IfCondition(LaunchConfiguration('rover')),
             parameters=[{
                 'mission_file': mission,
                 'max_speed': LaunchConfiguration('max_speed'),
                 'dropout_every_s': LaunchConfiguration('dropout_every_s'),
                 'dropout_duration_s': LaunchConfiguration('dropout_duration_s'),
             }]),
        Node(package='loop_s2_gui', executable='console', output='screen'),
    ])
