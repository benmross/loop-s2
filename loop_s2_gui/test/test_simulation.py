"""The mission logic and the link model, without ROS or a display.

Run from the repository root with ``python3 -m pytest loop_s2_gui/test``.
"""

import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))

from loop_s2_gui.simulation import (ABORTED, ACTIVE, AUTONOMOUS, LIGHT_BLUE,  # noqa: E402
                                    LIGHT_FLASHING_GREEN, LIGHT_RED, REACHED, SKIPPED,
                                    Mission, RoverSim)

SPEC = yaml.safe_load(open(os.path.join(HERE, '..', 'config', 'mission.yaml')))


def fresh():
    mission = Mission(SPEC)
    return mission, RoverSim(mission, seed=1, max_speed=2.0)


def drive(rover, seconds, dt=0.05):
    for _ in range(int(seconds / dt)):
        rover.step(dt)


def test_mission_matches_the_urc_leg_mix():
    mission = Mission(SPEC)
    kinds = [leg.kind for leg in mission.legs]
    assert len(mission.legs) == 7
    assert kinds.count(0) == 2, 'two GNSS-only waypoints'
    assert kinds.count(1) == 3, 'three AR posts'
    assert kinds.count(2) == 2, 'two unmarked objects'


def test_coordinates_round_trip_through_the_local_frame():
    mission = Mission(SPEC)
    lat, lon = mission.latlon(100.0, 200.0)
    assert abs(lat - mission.origin[0]) < 0.01 and lat > mission.origin[0]
    assert lon > mission.origin[1]


def test_starting_a_leg_drives_to_it_and_signals_arrival():
    mission, rover = fresh()
    ok, _ = rover.start_leg(0)
    assert ok and rover.mode == AUTONOMOUS and rover.light == LIGHT_RED
    assert mission.legs[0].status == ACTIVE
    for _ in range(4000):
        rover.step(0.05)
        if mission.legs[0].status == REACHED:
            break
    assert mission.legs[0].status == REACHED, 'it should reach a 69 m leg inside 200 s'
    assert rover.light == LIGHT_FLASHING_GREEN, 'the rules want flashing green on arrival'
    assert rover.speed == 0.0
    drive(rover, 8)
    assert rover.light != LIGHT_FLASHING_GREEN, 'and it stops flashing afterwards'


def test_abort_stops_the_rover_and_refuses_to_start_again():
    mission, rover = fresh()
    rover.start_leg(0)
    drive(rover, 10)
    assert rover.speed > 0.0
    rover.abort()
    assert rover.mode == ABORTED and rover.light == LIGHT_BLUE
    assert mission.legs[0].status != ACTIVE
    ok, detail = rover.start_leg(1)
    assert not ok and 'resume' in detail
    ok, _ = rover.resume_teleop()
    assert ok and rover.start_leg(1)[0]


def test_skip_and_speed_limits_are_checked():
    mission, rover = fresh()
    assert rover.skip_leg(2)[0] and mission.legs[2].status == SKIPPED
    assert not rover.set_max_speed(9.0)[0]
    assert rover.set_max_speed(0.6)[0] and rover.max_speed == 0.6


def test_the_link_fades_with_distance_and_goes_silent_far_out():
    mission, rover = fresh()
    near = rover.rssi_dbm()
    rover.east, rover.north = 900.0, 900.0
    assert rover.rssi_dbm() < near - 20
    rover.terrain_loss = 14.0
    assert not rover.link_up(), 'far enough away, nothing gets through'


def test_a_scheduled_dropout_silences_telemetry():
    mission = Mission(SPEC)
    rover = RoverSim(mission, seed=2, dropout_every_s=20.0, dropout_duration_s=5.0)
    rover.elapsed = 1.0
    assert not rover.link_up()
    rover.elapsed = 10.0
    assert rover.link_up()
