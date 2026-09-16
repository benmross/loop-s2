"""A rover that answers the console: telemetry out, commands in.

Stands in for the real thing. It drives itself to whichever leg the operator
starts, reports where it is at 5 Hz, and stops talking when the link to the
base station will not carry the message, which is the case the console has to
survive.
"""

import math

import rclpy
import yaml
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy

from loop_s2_gui.simulation import ABORTED, AUTONOMOUS, Mission, RoverSim
from loop_s2_msgs.msg import CommandAck, MissionLeg, MissionState, OperatorCommand, RoverTelemetry

TELEMETRY_QOS = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT)
STATE_QOS = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                       durability=DurabilityPolicy.TRANSIENT_LOCAL)
COMMAND_QOS = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)


class RoverSimNode(Node):

    def __init__(self):
        super().__init__('rover_sim')
        param = self.declare_parameter
        mission_file = param('mission_file', '').value
        telemetry_rate = param('telemetry_rate', 5.0).value
        state_rate = param('state_rate', 2.0).value
        max_speed = param('max_speed', 1.2).value
        seed = param('seed', 0).value
        dropout_every_s = param('dropout_every_s', 0.0).value
        dropout_duration_s = param('dropout_duration_s', 0.0).value
        if not mission_file:
            raise RuntimeError('the mission_file parameter is required')

        with open(mission_file) as f:
            self.mission = Mission(yaml.safe_load(f))
        self.rover = RoverSim(self.mission, seed=seed or None, max_speed=max_speed,
                              dropout_every_s=dropout_every_s,
                              dropout_duration_s=dropout_duration_s)
        self.dropped = 0

        self.telemetry_pub = self.create_publisher(RoverTelemetry, 'rover/telemetry',
                                                   TELEMETRY_QOS)
        self.state_pub = self.create_publisher(MissionState, 'mission/state', STATE_QOS)
        self.ack_pub = self.create_publisher(CommandAck, 'operator/command_ack', COMMAND_QOS)
        self.create_subscription(OperatorCommand, 'operator/command', self._on_command,
                                 COMMAND_QOS)
        self.create_timer(0.05, lambda: self.rover.step(0.05))
        self.create_timer(1.0 / telemetry_rate, self._publish_telemetry)
        self.create_timer(1.0 / state_rate, self._publish_state)
        self.get_logger().info(
            f'{self.mission.name}: {len(self.mission.legs)} legs, '
            f'{self.mission.time_limit_s / 60:.0f} minute limit')
        if dropout_every_s > 0:
            self.get_logger().info(
                f'Scheduled link dropouts: {dropout_duration_s:.0f} s every '
                f'{dropout_every_s:.0f} s')

    def _on_command(self, msg):
        handlers = {
            OperatorCommand.START_LEG: lambda: self.rover.start_leg(msg.leg_id),
            OperatorCommand.SKIP_LEG: lambda: self.rover.skip_leg(msg.leg_id),
            OperatorCommand.ABORT: self.rover.abort,
            OperatorCommand.RESUME_TELEOP: self.rover.resume_teleop,
            OperatorCommand.SET_MAX_SPEED: lambda: self.rover.set_max_speed(msg.value),
        }
        handler = handlers.get(msg.command)
        if handler is None:
            accepted, detail = False, f'unknown command {msg.command}'
        else:
            accepted, detail = handler()
        level = self.get_logger().info if accepted else self.get_logger().warn
        level(f'command {msg.sequence} from {msg.issued_by}: {detail}')

        ack = CommandAck()
        ack.header.stamp = self.get_clock().now().to_msg()
        ack.sequence = msg.sequence
        ack.accepted = accepted
        ack.detail = detail
        self.ack_pub.publish(ack)
        self._publish_state()

    def _publish_telemetry(self):
        if not self.rover.link_up():
            self.dropped += 1
            self.get_logger().warn(
                f'link down, telemetry not sent ({self.dropped} messages dropped)',
                throttle_duration_sec=2.0)
            return
        rover = self.rover
        distance, bearing = rover.distance_to_target()
        lat, lon = self.mission.latlon(rover.east, rover.north)
        msg = RoverTelemetry()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'base_station'
        msg.latitude = lat
        msg.longitude = lon
        msg.fix_type = rover.fix_type
        msg.satellites = rover.satellites
        msg.heading_deg = float(math.degrees(rover.heading) % 360.0)
        msg.speed_mps = float(rover.speed)
        msg.east_m = float(rover.east)
        msg.north_m = float(rover.north)
        msg.distance_to_target_m = float(distance)
        msg.bearing_to_target_deg = float(bearing)
        msg.battery_pct = float(rover.battery_pct)
        msg.battery_voltage = float(22.2 + 3.2 * rover.battery_pct / 100.0)
        msg.link_rssi_dbm = float(rover.rssi_dbm())
        self.telemetry_pub.publish(msg)

    def _publish_state(self):
        if not self.rover.link_up():
            return
        rover = self.rover
        msg = MissionState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.mode = rover.mode
        msg.signal_light = rover.light
        msg.active_leg = int(rover.active_leg)
        msg.mission_elapsed_s = float(rover.elapsed)
        msg.mission_limit_s = float(self.mission.time_limit_s)
        msg.max_speed_mps = float(rover.max_speed)
        for leg in self.mission.legs:
            out = MissionLeg()
            out.id = leg.id
            out.label = leg.label
            out.type = leg.kind
            out.status = leg.status
            out.latitude, out.longitude = self.mission.latlon(leg.east_m, leg.north_m)
            out.tolerance_m = float(leg.tolerance_m)
            msg.legs.append(out)
        self.state_pub.publish(msg)


def main():
    rclpy.init()
    node = RoverSimNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
