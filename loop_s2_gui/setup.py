from glob import glob

from setuptools import find_packages, setup

package_name = 'loop_s2_gui'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Ben Ross',
    maintainer_email='ben.m.ross08@gmail.com',
    description='PyQt operator console for the URC Autonomous Navigation Mission',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'console = loop_s2_gui.console:main',
            'rover_sim = loop_s2_gui.rover_sim:main',
        ],
    },
)
