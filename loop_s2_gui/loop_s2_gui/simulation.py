"""The rover, the mission and the radio link, with no ROS and no Qt in them.

Keeping this plain makes the parts worth testing testable: whether arrival is
detected, whether an aborted rover refuses to drive, and whether the link
degrades with distance the way the console assumes it does.
"""

import math
import random

EARTH_R = 6378137.0

TYPE_GNSS, TYPE_POST, TYPE_OBJECT = 0, 1, 2
TYPE_NAMES = {TYPE_GNSS: 'GNSS', TYPE_POST: 'AR POST', TYPE_OBJECT: 'OBJECT'}
TYPE_CODES = {'gnss': TYPE_GNSS, 'post': TYPE_POST, 'object': TYPE_OBJECT}

PENDING, ACTIVE, REACHED, SKIPPED, FAILED = 0, 1, 2, 3, 4
STATUS_NAMES = {PENDING: 'PENDING', ACTIVE: 'ACTIVE', REACHED: 'REACHED',
                SKIPPED: 'SKIPPED', FAILED: 'FAILED'}

IDLE, AUTONOMOUS, TELEOP, ABORTED = 0, 1, 2, 3
MODE_NAMES = {IDLE: 'IDLE', AUTONOMOUS: 'AUTONOMOUS', TELEOP: 'TELEOP', ABORTED: 'ABORTED'}

LIGHT_OFF, LIGHT_RED, LIGHT_BLUE, LIGHT_FLASHING_GREEN = 0, 1, 2, 3

FIX_NONE, FIX_SINGLE, FIX_DGPS, FIX_RTK_FLOAT, FIX_RTK_FIXED = 0, 1, 2, 3, 4
FIX_NAMES = {FIX_NONE: 'NO FIX', FIX_SINGLE: 'SINGLE', FIX_DGPS: 'DGPS',
             FIX_RTK_FLOAT: 'RTK FLOAT', FIX_RTK_FIXED: 'RTK FIXED'}


class Leg:

    def __init__(self, leg_id, label, kind, east_m, north_m, tolerance_m):
        self.id = leg_id
        self.label = label
        self.kind = kind
        self.east_m = east_m
        self.north_m = north_m
        self.tolerance_m = tolerance_m
        self.status = PENDING


class Mission:
    """The leg list, and the local frame the console draws in.

    The rules give each leg as coordinates, so the console shows coordinates.
    Everything geometric happens in metres east and north of the base station,
    which is where an operator actually thinks from.
    """

    def __init__(self, spec):
        m = spec['mission']
        self.name = m.get('name', 'Autonomous Navigation Mission')
        self.time_limit_s = float(m.get('time_limit_s', 1800.0))
        self.origin = (float(m['origin']['latitude']), float(m['origin']['longitude']))
        self.legs = [
            Leg(i, leg['label'], TYPE_CODES[leg['type']], float(leg['east_m']),
                float(leg['north_m']), float(leg.get('tolerance_m', 3.0)))
            for i, leg in enumerate(spec['legs'])
        ]

    def leg(self, leg_id):
        return self.legs[leg_id] if 0 <= leg_id < len(self.legs) else None

    def latlon(self, east_m, north_m):
        lat0, lon0 = self.origin
        lat = lat0 + math.degrees(north_m / EARTH_R)
        lon = lon0 + math.degrees(east_m / (EARTH_R * math.cos(math.radians(lat0))))
        return lat, lon


class RoverSim:
    """A rover that drives itself to the active leg, and the radio it talks on.

    It exists so the console has something real to talk to. The console does
    not know it is a simulation: it subscribes and publishes the same
    messages a rover would.
    """

    def __init__(self, mission, seed=None, max_speed=1.2, turn_rate=0.8,
                 dropout_every_s=0.0, dropout_duration_s=0.0):
        self.mission = mission
        self.rng = random.Random(seed)
        self.max_speed = max_speed
        self.turn_rate = turn_rate
        self.dropout_every_s = dropout_every_s
        self.dropout_duration_s = dropout_duration_s

        self.east = 0.0
        self.north = 0.0
        self.heading = 0.0          # radians, 0 = north, clockwise positive
        self.speed = 0.0
        self.mode = IDLE
        self.light = LIGHT_OFF
        self.active_leg = -1
        self.battery_pct = 96.0
        self.elapsed = 0.0
        self.flash_until = 0.0
        self.terrain_loss = 4.0
        self.fix_type = FIX_RTK_FIXED
        self.satellites = 21

    # Commands

    def start_leg(self, leg_id):
        leg = self.mission.leg(leg_id)
        if leg is None:
            return False, f'no leg {leg_id}'
        if self.mode == ABORTED:
            return False, 'mission aborted, resume before starting a leg'
        if leg.status == REACHED:
            return False, f'{leg.label} already reached'
        if self.active_leg >= 0:
            self.mission.leg(self.active_leg).status = PENDING
        leg.status = ACTIVE
        self.active_leg = leg_id
        self.mode = AUTONOMOUS
        self.light = LIGHT_RED
        return True, f'driving to {leg.label}'

    def skip_leg(self, leg_id):
        leg = self.mission.leg(leg_id)
        if leg is None:
            return False, f'no leg {leg_id}'
        if leg.status == REACHED:
            return False, f'{leg.label} already reached'
        leg.status = SKIPPED
        if self.active_leg == leg_id:
            self._stand_down()
        return True, f'{leg.label} skipped'

    def abort(self):
        if self.active_leg >= 0:
            self.mission.leg(self.active_leg).status = PENDING
        self._stand_down()
        self.mode = ABORTED
        self.light = LIGHT_BLUE
        return True, 'autonomy stopped, rover held'

    def resume_teleop(self):
        self.mode = TELEOP
        self.light = LIGHT_BLUE
        return True, 'rover under manual control'

    def set_max_speed(self, value):
        if not 0.1 <= value <= 3.0:
            return False, f'{value:.2f} m/s out of range'
        self.max_speed = value
        return True, f'speed limit {value:.2f} m/s'

    def _stand_down(self):
        self.active_leg = -1
        self.speed = 0.0
        self.mode = IDLE
        if self.light != LIGHT_FLASHING_GREEN:
            self.light = LIGHT_OFF

    # Physics

    def step(self, dt):
        self.elapsed += dt
        if self.light == LIGHT_FLASHING_GREEN and self.elapsed > self.flash_until:
            self.light = LIGHT_RED if self.mode == AUTONOMOUS else LIGHT_OFF

        leg = self.mission.leg(self.active_leg) if self.active_leg >= 0 else None
        if leg is None or self.mode != AUTONOMOUS:
            self.speed = max(0.0, self.speed - 1.5 * dt)
        else:
            de, dn = leg.east_m - self.east, leg.north_m - self.north
            distance = math.hypot(de, dn)
            if distance <= leg.tolerance_m:
                leg.status = REACHED
                self.light = LIGHT_FLASHING_GREEN
                self.flash_until = self.elapsed + 6.0
                self._stand_down()
            else:
                wanted = math.atan2(de, dn)
                error = math.atan2(math.sin(wanted - self.heading), math.cos(wanted - self.heading))
                self.heading += max(-self.turn_rate * dt, min(self.turn_rate * dt, error))
                # Ground that is never as flat as the plan assumes.
                self.heading += self.rng.gauss(0.0, 0.25) * dt
                target_speed = self.max_speed * max(0.15, math.cos(min(abs(error), math.pi / 2)))
                self.speed += max(-1.0 * dt, min(0.6 * dt, target_speed - self.speed))
                self.east += math.sin(self.heading) * self.speed * dt
                self.north += math.cos(self.heading) * self.speed * dt

        self.battery_pct = max(0.0, self.battery_pct - (0.004 + 0.02 * self.speed) * dt)
        self.terrain_loss = min(14.0, max(0.0, self.terrain_loss + self.rng.gauss(0.0, 1.2) * dt))
        if self.rng.random() < 0.02 * dt:
            self.fix_type = self.rng.choice([FIX_RTK_FIXED, FIX_RTK_FIXED, FIX_RTK_FLOAT, FIX_DGPS])
            self.satellites = self.rng.randint(14, 24)

    # The link

    def rssi_dbm(self):
        """Signal at the rover. Free space loss plus whatever the ground adds."""
        distance = max(math.hypot(self.east, self.north), 1.0)
        return -38.0 - 22.0 * math.log10(distance) - self.terrain_loss

    def link_up(self):
        """Whether this telemetry message gets through at all.

        Below about -95 dBm packets start going missing, and below -104 dBm
        nothing arrives. A forced dropout can be scheduled on top of that, so
        a demonstration does not depend on the rover happening to drive far
        enough away.
        """
        if self.dropout_every_s > 0.0:
            phase = self.elapsed % self.dropout_every_s
            if phase < self.dropout_duration_s:
                return False
        rssi = self.rssi_dbm()
        if rssi > -95.0:
            return True
        if rssi < -104.0:
            return False
        return self.rng.random() > (-95.0 - rssi) / 9.0

    def distance_to_target(self):
        leg = self.mission.leg(self.active_leg) if self.active_leg >= 0 else None
        if leg is None:
            return -1.0, 0.0
        de, dn = leg.east_m - self.east, leg.north_m - self.north
        return math.hypot(de, dn), (math.degrees(math.atan2(de, dn)) + 360.0) % 360.0
