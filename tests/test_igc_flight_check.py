from pilot.track import Track
from datetime import datetime, date
from pilot.flightresult import FlightResult
from pilot.waypointachieved import WaypointAchieved
import factory_objects

test_task = factory_objects.test_task()


def test_track_read():
    test_track = Track.read_file('/app/tests/data/test_igc_1.igc', par_id=1)
    assert len(test_track.fixes) == 13856
    assert test_track.date == date(2019, 3, 9)
    assert test_track.gnss_alt_valid
    assert test_track.press_alt_valid
    assert test_track.flight.valid
    assert len(test_track.flight.fixes)
    assert test_track.flight.glider_type == 'OZONE Zeno'
    assert test_track.flight.date_timestamp == 1552089600.0


def test_track_flight_check():
    test_track = Track.read_file('/app/tests/data/test_igc_2.igc', par_id=1)
    test_result = FlightResult.check_flight(test_track.flight, test_task)
    assert int(test_result.distance_flown) == 64360
    assert test_result.best_waypoint_achieved == 'Goal'
    assert len(test_result.waypoints_achieved) == test_result.waypoints_made
    assert test_result.SSS_time == 41400
    assert test_result.ESS_time == 50555
    assert test_result.ESS_altitude == 880.0
    assert test_result.real_start_time == 41428
    assert test_result.flight_time == 12158.0
    achieved = test_result.waypoints_achieved[1]
    assert achieved.name == 'TP01'
    assert achieved.rawtime == 43947
    assert achieved.altitude == 1445.0
    assert achieved.lat == 45.814566666666664
    assert achieved.lon == 9.7707166666666
