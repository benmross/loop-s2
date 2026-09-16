"""The operator console: a PyQt window that is also a ROS 2 node.

During the Autonomous Navigation Mission the operator sits in the control
station with no view of the course, so this window is the only thing they can
see. It shows what the rover is doing and lets them start a leg, skip one,
cap the speed, or stop the rover. It does not let them drive: the rules do
not allow a human to help while the rover is driving itself.

Everything on screen carries its own age. If telemetry stops arriving the
console says so loudly rather than leaving the last good numbers up, because
a number that has quietly stopped changing is worse than no number at all.
"""

import sys
import time

import rclpy
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QKeySequence
from PyQt5.QtWidgets import (QApplication, QGridLayout, QHBoxLayout, QLabel, QMainWindow,
                             QPushButton, QShortcut, QSlider, QVBoxLayout, QWidget)
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy

from loop_s2_gui import theme
from loop_s2_gui.simulation import (ABORTED, AUTONOMOUS, FIX_NAMES, FIX_RTK_FIXED, IDLE,
                                    LIGHT_BLUE, LIGHT_FLASHING_GREEN, LIGHT_RED,
                                    MODE_NAMES, TELEOP)
from loop_s2_gui.widgets import EventLog, LegTable, MapView, SignalLight, StatusTile, panel
from loop_s2_msgs.msg import CommandAck, MissionState, OperatorCommand, RoverTelemetry

TELEMETRY_QOS = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT)
STATE_QOS = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                       durability=DurabilityPolicy.TRANSIENT_LOCAL)
COMMAND_QOS = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)

STALE_S = 1.5      # telemetry arrives at 5 Hz; this is several missed messages
LOST_S = 4.0
RESEND_S = 1.2
MAX_ATTEMPTS = 3

COMMAND_NAMES = {OperatorCommand.START_LEG: 'START LEG', OperatorCommand.SKIP_LEG: 'SKIP LEG',
                 OperatorCommand.ABORT: 'ABORT', OperatorCommand.RESUME_TELEOP: 'RESUME',
                 OperatorCommand.SET_MAX_SPEED: 'SPEED LIMIT'}


class Pending:

    def __init__(self, msg, description):
        self.msg = msg
        self.description = description
        self.sent_at = time.monotonic()
        self.attempts = 1


class ConsoleNode(Node):
    """The ROS half: subscribes to the rover, publishes what the operator asks.

    Commands are resent until the rover acknowledges them, because a command
    that vanishes into a dead radio link should not look the same as one the
    rover refused.
    """

    def __init__(self, operator='operator'):
        super().__init__('operator_console')
        self.operator = operator
        self.telemetry = None
        self.telemetry_at = 0.0
        self.state = None
        self.state_at = 0.0
        self.pending = {}
        self.events = []
        self._sequence = 0

        self.create_subscription(RoverTelemetry, 'rover/telemetry', self._on_telemetry,
                                 TELEMETRY_QOS)
        self.create_subscription(MissionState, 'mission/state', self._on_state, STATE_QOS)
        self.create_subscription(CommandAck, 'operator/command_ack', self._on_ack, COMMAND_QOS)
        self.commands = self.create_publisher(OperatorCommand, 'operator/command', COMMAND_QOS)
        self.create_timer(0.25, self._retry)

    def _on_telemetry(self, msg):
        self.telemetry = msg
        self.telemetry_at = time.monotonic()

    def _on_state(self, msg):
        self.state = msg
        self.state_at = time.monotonic()

    def _on_ack(self, msg):
        pending = self.pending.pop(msg.sequence, None)
        name = pending.description if pending else f'command {msg.sequence}'
        if msg.accepted:
            self.event(f'{name}: {msg.detail}', 'ok')
        else:
            self.event(f'{name} REFUSED: {msg.detail}', 'fault')

    def event(self, text, level='info'):
        self.events.append((time.strftime('%H:%M:%S'), text, level))

    def send(self, command, leg_id=-1, value=0.0, description=None):
        self._sequence += 1
        msg = OperatorCommand()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.sequence = self._sequence
        msg.command = command
        msg.leg_id = int(leg_id)
        msg.value = float(value)
        msg.issued_by = self.operator
        self.commands.publish(msg)
        description = description or COMMAND_NAMES.get(command, 'command')
        self.pending[msg.sequence] = Pending(msg, description)
        self.event(f'{description} sent', 'sent')

    def _retry(self):
        now = time.monotonic()
        for sequence, pending in list(self.pending.items()):
            if now - pending.sent_at < RESEND_S:
                continue
            if pending.attempts >= MAX_ATTEMPTS:
                del self.pending[sequence]
                self.event(f'{pending.description}: NO ACKNOWLEDGEMENT after '
                           f'{MAX_ATTEMPTS} attempts, rover may not have it', 'fault')
                continue
            pending.attempts += 1
            pending.sent_at = now
            self.commands.publish(pending.msg)
            self.event(f'{pending.description}: no ack, resent '
                       f'({pending.attempts}/{MAX_ATTEMPTS})', 'warn')

    def telemetry_age(self):
        return time.monotonic() - self.telemetry_at if self.telemetry else None

    def state_age(self):
        return time.monotonic() - self.state_at if self.state else None


class Console(QMainWindow):

    def __init__(self, node):
        super().__init__()
        self.node = node
        self.setWindowTitle('URC Operator Console - Autonomous Navigation')
        self.resize(1560, 940)
        self.setStyleSheet(theme.STYLESHEET)
        self._build()

        self._events_shown = 0
        self._last_speed_sent = None
        refresh = QTimer(self)
        refresh.timeout.connect(self._refresh)
        refresh.start(100)
        spin = QTimer(self)
        spin.timeout.connect(self._spin)
        spin.start(10)

    # Layout

    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)
        outer.addWidget(self._header())

        middle = QHBoxLayout()
        middle.setSpacing(10)
        middle.addWidget(self._left_column(), 6)
        middle.addWidget(self._map_panel(), 6)
        middle.addWidget(self._telemetry_panel(), 3)
        outer.addLayout(middle, 1)

        log_panel, log_layout = panel('MISSION LOG')
        self.log = EventLog()
        log_layout.addWidget(self.log)
        outer.addWidget(log_panel)

    def _header(self):
        frame, layout = panel()
        layout.setContentsMargins(16, 10, 16, 10)
        row = QHBoxLayout()
        row.setSpacing(18)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title = QLabel('AUTONOMOUS NAVIGATION MISSION')
        title.setObjectName('bannerTitle')
        subtitle = QLabel('operator console, control station (no view of course)')
        subtitle.setStyleSheet(f'color: {theme.DIM}; font-size: 11px;')
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        row.addLayout(title_box)
        row.addStretch(1)

        self.clock = QLabel('--:--')
        self.clock.setObjectName('clock')
        clock_box = QVBoxLayout()
        clock_box.setSpacing(0)
        clock_label = QLabel('MISSION TIME REMAINING')
        clock_label.setObjectName('tileTitle')
        clock_box.addWidget(clock_label)
        clock_box.addWidget(self.clock)
        row.addLayout(clock_box)
        row.addStretch(1)

        self.mode_label = QLabel('MODE --')
        self.mode_label.setStyleSheet('font-size: 16px; font-weight: 700;')
        row.addWidget(self.mode_label)

        light_box = QVBoxLayout()
        light_box.setSpacing(2)
        light_title = QLabel('ROVER LIGHT')
        light_title.setObjectName('tileTitle')
        light_box.addWidget(light_title)
        self.light = SignalLight()
        light_box.addWidget(self.light, alignment=Qt.AlignHCenter)
        row.addLayout(light_box)

        self.light_text = QLabel('--')
        self.light_text.setStyleSheet(f'color: {theme.DIM}; font-size: 11px;')
        row.addWidget(self.light_text)

        layout.addLayout(row)
        return frame

    def _left_column(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        legs_panel, legs_layout = panel('MISSION PLAN')
        self.legs = LegTable()
        legs_layout.addWidget(self.legs)
        layout.addWidget(legs_panel, 1)

        commands, command_layout = panel('COMMANDS')
        buttons = QGridLayout()
        buttons.setSpacing(8)
        self.start_button = QPushButton('START SELECTED LEG')
        self.start_button.setObjectName('primary')
        self.start_button.clicked.connect(self._start_leg)
        self.skip_button = QPushButton('SKIP LEG')
        self.skip_button.clicked.connect(self._skip_leg)
        self.resume_button = QPushButton('RESUME (MANUAL)')
        self.resume_button.clicked.connect(self._resume)
        buttons.addWidget(self.start_button, 0, 0, 1, 2)
        buttons.addWidget(self.skip_button, 1, 0)
        buttons.addWidget(self.resume_button, 1, 1)
        command_layout.addLayout(buttons)

        speed_row = QHBoxLayout()
        speed_label = QLabel('SPEED LIMIT')
        speed_label.setObjectName('tileTitle')
        self.speed = QSlider(Qt.Horizontal)
        self.speed.setRange(2, 30)          # 0.2 to 3.0 m/s
        self.speed.setValue(12)
        self.speed_value = QLabel('1.20 m/s')
        self.speed_value.setFont(QFont(theme.MONO, 12, QFont.Bold))
        # Any change sends, whether it came from a drag, a click on the
        # groove or the arrow keys, but only once the operator has settled on
        # a number: a drag across the range should not send twenty commands.
        self._speed_timer = QTimer(self)
        self._speed_timer.setSingleShot(True)
        self._speed_timer.setInterval(350)
        self._speed_timer.timeout.connect(self._send_speed)
        self.speed.valueChanged.connect(self._speed_changed)
        speed_row.addWidget(speed_label)
        speed_row.addWidget(self.speed, 1)
        speed_row.addWidget(self.speed_value)
        command_layout.addLayout(speed_row)

        self.abort_button = QPushButton('ABORT AUTONOMY  (SPACE)')
        self.abort_button.setObjectName('abort')
        self.abort_button.clicked.connect(self._abort)
        command_layout.addWidget(self.abort_button)
        QShortcut(QKeySequence(Qt.Key_Space), self, self._abort)
        layout.addWidget(commands)
        return container

    def _map_panel(self):
        frame, layout = panel('COURSE, LOOKING DOWN')
        self.map = MapView()
        layout.addWidget(self.map, 1)
        return frame

    def _telemetry_panel(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        link_panel, link_layout = panel('LINK')
        self.link_tile = StatusTile('telemetry', 'age of the newest message')
        self.rssi_tile = StatusTile('signal at rover', 'received strength')
        self.ack_tile = StatusTile('commands', 'waiting for acknowledgement')
        for tile in (self.link_tile, self.rssi_tile, self.ack_tile):
            link_layout.addWidget(tile)
        layout.addWidget(link_panel)

        nav_panel, nav_layout = panel('NAVIGATION')
        self.target_tile = StatusTile('distance to target', 'current leg')
        self.bearing_tile = StatusTile('bearing / heading', 'degrees true')
        self.speed_tile = StatusTile('ground speed', 'limit set by operator')
        self.fix_tile = StatusTile('gnss fix', 'satellites')
        self.position_tile = StatusTile('position', 'latitude, longitude')
        for tile in (self.target_tile, self.bearing_tile, self.speed_tile, self.fix_tile,
                     self.position_tile):
            nav_layout.addWidget(tile)
        layout.addWidget(nav_panel)

        power_panel, power_layout = panel('POWER')
        self.battery_tile = StatusTile('battery', 'pack voltage')
        power_layout.addWidget(self.battery_tile)
        layout.addWidget(power_panel)
        layout.addStretch(1)
        return container

    # Commands

    def _selected(self):
        leg = self.legs.selected_leg()
        if leg is None:
            self.node.event('no leg selected', 'warn')
        return leg

    def _start_leg(self):
        leg = self._selected()
        if leg is not None:
            self.node.send(OperatorCommand.START_LEG, leg_id=leg,
                           description=f'START LEG {leg + 1}')

    def _skip_leg(self):
        leg = self._selected()
        if leg is not None:
            self.node.send(OperatorCommand.SKIP_LEG, leg_id=leg,
                           description=f'SKIP LEG {leg + 1}')

    def _abort(self):
        self.node.send(OperatorCommand.ABORT, description='ABORT')

    def _resume(self):
        self.node.send(OperatorCommand.RESUME_TELEOP, description='RESUME MANUAL')

    def _speed_changed(self, value):
        self.speed_value.setText(f'{value / 10:.2f} m/s')
        self._speed_timer.start()

    def _send_speed(self):
        value = self.speed.value() / 10.0
        self.node.send(OperatorCommand.SET_MAX_SPEED, value=value,
                       description=f'SPEED LIMIT {value:.2f} m/s')

    # Refresh

    def _spin(self):
        """Pump ROS from the Qt loop, and close if ROS goes away underneath.

        Without this the window survives its own node: on shutdown the
        context goes invalid, every spin raises, and an operator is left
        looking at a console that has quietly stopped being connected to
        anything.
        """
        if not rclpy.ok():
            return self._ros_gone('ROS was shut down')
        try:
            rclpy.spin_once(self.node, timeout_sec=0.0)
        except Exception as exc:                                  # noqa: BLE001
            self._ros_gone(f'ROS stopped: {exc}')

    def _ros_gone(self, reason):
        print(f'console closing: {reason}', file=sys.stderr)
        QApplication.quit()

    def _refresh(self):
        for clock, text, level in self.node.events[self._events_shown:]:
            self.log.log(clock, text, level)
        self._events_shown = len(self.node.events)

        age = self.node.telemetry_age()
        lost = age is None or age > LOST_S
        stale = age is not None and age > STALE_S
        self._refresh_link(age, stale, lost)
        self._refresh_state()
        self._refresh_telemetry(lost, stale)

    def _refresh_link(self, age, stale, lost):
        if age is None:
            self.link_tile.set('NO DATA', 'fault', 'nothing received yet')
        elif lost:
            self.link_tile.set(f'LOST {age:0.1f}s', 'fault', 'telemetry has stopped')
        elif stale:
            self.link_tile.set(f'{age:0.1f}s', 'warn', 'messages are being missed')
        else:
            self.link_tile.set(f'{age:0.1f}s', 'ok', 'live')

        pending = len(self.node.pending)
        if pending:
            self.ack_tile.set(str(pending), 'warn', 'awaiting acknowledgement')
        else:
            self.ack_tile.set('CLEAR', 'ok', 'all commands acknowledged')

    def _refresh_state(self):
        state = self.node.state
        if state is None:
            self.mode_label.setText('MODE  --')
            return
        mode_color = {AUTONOMOUS: theme.FAULT, TELEOP: theme.INFO, ABORTED: theme.FAULT,
                      IDLE: theme.DIM}.get(state.mode, theme.DIM)
        self.mode_label.setText(f'MODE  {MODE_NAMES.get(state.mode, "?")}')
        self.mode_label.setStyleSheet(
            f'font-size: 16px; font-weight: 700; color: {mode_color};')
        self.light.set_state(state.signal_light)
        self.light_text.setText({LIGHT_RED: 'RED\nautonomous', LIGHT_BLUE: 'BLUE\nmanual',
                                 LIGHT_FLASHING_GREEN: 'FLASHING GREEN\narrived'}
                                .get(state.signal_light, 'OFF\nstopped'))

        remaining = max(0.0, state.mission_limit_s - state.mission_elapsed_s)
        self.clock.setText(f'{int(remaining // 60):02d}:{int(remaining % 60):02d}')
        color = theme.OK if remaining > 300 else theme.WARN if remaining > 60 else theme.FAULT
        self.clock.setStyleSheet(f'color: {color};')

        legs = []
        for leg in state.legs:
            legs.append({'id': leg.id, 'label': leg.label, 'kind': leg.type,
                         'status': leg.status, 'latitude': leg.latitude,
                         'longitude': leg.longitude, 'tolerance': leg.tolerance_m,
                         'east': 0.0, 'north': 0.0})
        self.legs.set_legs(legs)
        self._legs_for_map(legs, state)
        self.abort_button.setEnabled(state.mode != ABORTED)

    def _legs_for_map(self, legs, state):
        telemetry = self.node.telemetry
        if telemetry is None:
            return
        # Legs are carried as coordinates; the map works in metres, so convert
        # against the rover's own position report.
        for leg, source in zip(legs, state.legs):
            leg['east'], leg['north'] = _to_local(source.latitude, source.longitude,
                                                  telemetry.latitude, telemetry.longitude,
                                                  telemetry.east_m, telemetry.north_m)
        self.map.set_legs(legs)
        target = None
        if 0 <= state.active_leg < len(legs):
            target = (legs[state.active_leg]['east'], legs[state.active_leg]['north'])
        self.map.set_rover(telemetry.east_m, telemetry.north_m, telemetry.heading_deg, target)

    def _refresh_telemetry(self, lost, stale):
        telemetry = self.node.telemetry
        self.map.set_stale(lost)
        if telemetry is None or lost:
            for tile in (self.rssi_tile, self.target_tile, self.bearing_tile, self.speed_tile,
                         self.fix_tile, self.position_tile, self.battery_tile):
                tile.blank('no current telemetry')
            return
        state = 'stale' if stale else 'ok'

        rssi = telemetry.link_rssi_dbm
        rssi_state = 'ok' if rssi > -85 else 'warn' if rssi > -98 else 'fault'
        self.rssi_tile.set(f'{rssi:0.0f} dBm', rssi_state,
                           'strong' if rssi > -85 else 'marginal' if rssi > -98 else 'failing')

        if telemetry.distance_to_target_m < 0:
            self.target_tile.set('NO LEG', 'idle', 'no leg running')
        else:
            self.target_tile.set(f'{telemetry.distance_to_target_m:0.1f} m', state,
                                 'to the active leg')
        self.bearing_tile.set(f'{telemetry.bearing_to_target_deg:03.0f} / '
                              f'{telemetry.heading_deg:03.0f}', state, 'wanted / actual')
        limit = self.node.state.max_speed_mps if self.node.state else 0.0
        self.speed_tile.set(f'{telemetry.speed_mps:0.2f} m/s', state, f'limit {limit:0.2f} m/s')
        fix_state = 'ok' if telemetry.fix_type >= FIX_RTK_FIXED else 'warn'
        self.fix_tile.set(FIX_NAMES.get(telemetry.fix_type, '?'), fix_state,
                          f'{telemetry.satellites} satellites')
        self.position_tile.set(f'{telemetry.latitude:0.5f}, {telemetry.longitude:0.5f}', state,
                               f'{telemetry.east_m:0.0f} m E, {telemetry.north_m:0.0f} m N')
        battery = telemetry.battery_pct
        battery_state = 'ok' if battery > 40 else 'warn' if battery > 20 else 'fault'
        self.battery_tile.set(f'{battery:0.1f} %', battery_state,
                              f'{telemetry.battery_voltage:0.1f} V')


def _to_local(lat, lon, ref_lat, ref_lon, ref_east, ref_north):
    """Metres east and north of the rover's own reported position."""
    import math
    earth = 6378137.0
    east = math.radians(lon - ref_lon) * earth * math.cos(math.radians(ref_lat)) + ref_east
    north = math.radians(lat - ref_lat) * earth + ref_north
    return east, north


def main():
    rclpy.init()
    node = ConsoleNode()
    app = QApplication(sys.argv)
    window = Console(node)
    window.show()
    node.event('console up, waiting for the rover', 'info')
    try:
        app.exec_()
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
