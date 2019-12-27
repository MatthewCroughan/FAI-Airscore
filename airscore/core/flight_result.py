"""
Flight Result Library

contains Flight_result class.
contains statistics about a flight with regards to a task.

Methods:
    from_fsdb
    check_flight - check flight against task and record results (times, distances and leadout coeff)
    to_db - write result to DB (tblTaskResult) store_result_test - write result to DB in test mode(tblTaskResult_test)
    store_result_json - not needed, think we can delete
    to_geojson_result - create json file containing tracklog (split into preSSS, preGoal and postGoal), Thermals,
                        bounds and result obj
    save_result_file - save the json file.

Functions:
    verify_all_tracks   gets all task pilots and check all flights
    update_all_results  stores all results to database

- AirScore -
Stuart Mackintosh - Antonio Golfari
2019

"""

from calcUtils import get_datetime
from route import rawtime_float_to_hms, in_semicircle, distance_flown
from myconn import Database
import jsonpickle, json
from mapUtils import checkbbox


class Flight_result(object):
    """Set of statistics about a flight with respect a task.
    Attributes:
        start_time:     time the task was started . i.e relevant start gate. (local time)
        SSS_time:       array of time(s) the pilot started, i.e. crossed the start line (local time)
        waypoints achieved: the last waypoint achieved by the pilot, SSS, ESS, Goal or a waypoint number (wp1 is first wp after SSS)
        ESS_time:       the time the pilot crossed the ESS (local time)
        ss_time:        the length of time the pilot took to complete the course. ESS- Start_time (for Race) or ESS - SSS_time (for elapsed)
        fixed_LC:       fixed part of lead_coeff, indipendent from other tracks
        lead_coeff:     lead points coeff (for GAP based systems), sum of fixed_LC and variable part calculated during scoring
        """

    def __init__(self, par_id=None, first_time=None, real_start_time=None, SSS_time=0, ESS_time=None, goal_time=None,
                 last_time=None,
                 best_waypoint_achieved='No waypoints achieved', fixed_LC=0, lead_coeff=0, distance_flown=0,
                 last_altitude=0,
                 jump_the_gun=None, track_file=None):
        """

        :type lead_coeff: int
        """
        self.first_time = first_time
        self.real_start_time = real_start_time
        self.SSS_time = SSS_time
        self.ESS_time = ESS_time
        self.speed = 0
        self.goal_time = goal_time
        self.last_time = last_time
        self.best_waypoint_achieved = best_waypoint_achieved
        self.waypoints_achieved = []
        self.fixed_LC = fixed_LC
        self.lead_coeff = lead_coeff
        self.distance_flown = distance_flown
        self.total_distance = 0
        self.max_altitude = 0
        self.ESS_altitude = 0
        self.goal_altitude = 0
        self.last_altitude = last_altitude
        self.landing_time = 0
        self.landing_altitude = 0
        self.jump_the_gun = jump_the_gun
        self.result_type = 'lo'
        self.score = 0
        self.departure_score = 0
        self.arrival_score = 0
        self.distance_score = 0
        self.time_score = 0
        self.penalty = 0
        self.comment = None
        # self.ID = None  # Could delete?
        # self.par_id = par_id  # Could delete?
        # self.track_file = track_file  # Could delete?

    def __setattr__(self, attr, value):
        property_names = [p for p in dir(Flight_result) if isinstance(getattr(Flight_result, p), property)]
        if attr not in property_names:
            self.__dict__[attr] = value

    @property
    def ss_time(self):
        if self.ESS_time:
            return self.ESS_time - self.SSS_time
        else:
            return None

    @property
    def time(self):
        if self.ESS_time:
            return self.ESS_time - self.SSS_time
        else:
            return None

    @property
    def flight_time(self):
        if self.landing_time and self.first_time:
            return self.landing_time - self.first_time
        if self.last_time and self.first_time:
            return self.last_time - self.first_time
        else:
            return 0

    @property
    def distance(self):
        if self.distance_flown:
            return max(self.distance_flown, self.total_distance)
        else:
            return 0

    # @property
    # def time_after(self):
    #     if self.ESS_time:
    #         return self.ESS_time - self.SSS_time
    #     else:
    #         return 0

    @property
    def waypoints_made(self):
        from collections import Counter
        if self.waypoints_achieved:
            return len(Counter(el[0] for el in self.waypoints_achieved))
        else:
            return 0

    def as_dict(self):
        return self.__dict__

    @classmethod
    def from_fsdb(cls, res, SS_distance=None, dep=None, arr=None):
        """ Creates Results from FSDB FsPartecipant element, which is in xml format.
            Unfortunately the fsdb format isn't published so much of this is simply an
            exercise in reverse engineering.
        """
        from datetime import timedelta
        from calcUtils import string_to_seconds

        result = cls()
        result.ID = int(res.get('id'))
        if res.find('FsFlightData') is None and res.find('FsResult') is None:
            '''pilot is abs'''
            print(f"ID {result.ID}: ABS")
            result.result_type = 'abs'
            return result
        elif res.find('FsFlightData').get('distance') is None:
            if float(res.find('FsResult').get('distance')) > 0:
                '''pilot is min dist'''
                print(f"ID {result.ID}: Min Dist")
                result.result_type = 'mindist'
            else:
                '''pilot is dnf'''
                print(f"ID {result.ID}: DNF")
                result.result_type = 'dnf'
            return result

        d = res.find('FsFlightData')
        result.real_start_time = string_to_seconds(d.get('started_ss'))
        result.last_altitude = int(d.get('last_tracklog_point_alt')
                                   if d.get('last_tracklog_point_alt') is not None else 0)
        result.max_altitude = int(d.get('max_alt')
                                  if d.get('max_alt') is not None else 0)
        result.track_file = d.get('tracklog_filename')
        result.lead_coeff = None if d.get('lc') is None else float(d.get('lc'))
        if not d.get('finished_ss') == "":
            result.ESS_altitude = int(d.get('altitude_at_ess')
                                      if d.get('altitude_at_ess') is not None else 0)
        if d.get('reachedGoal') == "1":
            result.goal_time = string_to_seconds(d.get('finished_task'))
            result.result_type = 'goal'
        if res.find('FsResult') is not None:
            '''reading flight data'''
            r = res.find('FsResult')
            # result['rank'] = int(r.get('rank'))
            result.score = float(r.get('points'))
            result.total_distance = float(r.get('distance')) * 1000  # in meters
            result.distance_flown = float(r.get('real_distance')) * 1000  # in meters
            # print ("start_ss: {}".format(r.get('started_ss')))
            result.SSS_time = string_to_seconds(r.get('started_ss'))
            if result.SSS_time is not None:
                result.ESS_time = string_to_seconds(r.get('finished_ss'))
                if SS_distance is not None and result.ESS_time is not None and result.ESS_time > 0:
                    result.speed = (SS_distance / 1000) / ((result.ESS_time - result.SSS_time) / 3600)
            else:
                result.ESS_time = None
            result.last_altitude = int(r.get('last_altitude_above_goal'))
            result.distance_score = float(r.get('distance_points'))
            result.time_score = float(r.get('time_points'))
            result.penalty = 0  # fsdb score is already decreased by penalties
            if not r.get('penalty_reason') == "":
                if r.get('penalty') != "0":
                    result.comment = f"{float(r.get('penalty')) * 100}%: "
                else:
                    result.comment = f"{float(r.get('penalty_points'))} points: "
                result.comment += r.get('penalty_reason')
            if not r.get('penalty_reason_auto') == "":
                comment = f"{float(r.get('penalty_points_auto'))} points: "
                comment += r.get('penalty_reason_auto')
                if result.comment is None:
                    result.comment = comment
                else:
                    result.comment += ' - ' + comment
            if dep == 'on':
                result.departure_score = float(r.get('departure_points'))
            elif dep == 'leadout':
                result.departure_score = float(r.get('leading_points'))
            else:
                result.departure_score = 0  # not necessary as it it initialized to 0
            result.arrival_score = float(r.get('arrival_points')) if arr != 'off' else 0

        return result

    @staticmethod
    def read(res_id):
        """reads result from database"""
        from db_tables import FlightResultView as R

        result = Flight_result()
        with Database() as db:
            # get result details.
            q = db.session.query(R)
            db.populate_obj(result, q.get(res_id))
        return result

    @staticmethod
    def from_dict(d):
        result = Flight_result()
        for key, value in d.items():
            if hasattr(result, key):
                setattr(result, key, value)
        return result

    @classmethod
    def check_flight(cls, flight, task, lib, min_tol_m=0, deadline=None):
        """ Checks a Flight object against the task.
            Args:
                   flight:  a Flight object
                   task:    a Task
                   lib:     formula library
                   min_tol_m: minimum tolerance in meters, default is 0
                   deadline: in multiple start or elapsed time, I need to check again track using Min_flight_time
                                as deadline
            Returns:
                    a list of GNSSFixes of when turnpoints were achieved.
        """
        from route import start_made_civl, tp_made_civl, tp_time_civl

        ''' Altitude Source: '''
        alt_source = 'GPS' if task.formula.scoring_altitude is None else task.formula.scoring_altitude

        '''initialize'''
        result = cls()
        tolerance = task.tolerance
        time_offset = task.time_offset  # local time offset for result times (SSS and ESS)
        max_jump_the_gun = 0 if not task.formula.jump_the_gun else task.formula.max_JTG     # seconds

        if not task.optimised_turnpoints:
            task.calculate_optimised_task_length()
        distances2go = task.distances_to_go  # Total task Opt. Distance, in legs list
        best_dist_to_ess = [task.SS_distance]  # Best distance to ESS, for LC calculation
        waypoint = 1  # for report purpouses
        t = 0  # turnpoint pointer
        started = False  # check if pilot has a valid start fix

        result.first_time = flight.fixes[
            0].rawtime if not flight.takeoff_fix else flight.takeoff_fix.rawtime  # time of flight origin
        max_altitude = 0  # max altitude
        result.last_altitude = 0

        if task.stopped_time:
            if not deadline:
                '''Using stop_time (stopped_time - score_back_time)'''
                deadline = task.stop_time

        for i in range(len(flight.fixes) - 1):
            '''Get two consecutive trackpoints as needed to use FAI / CIVL rules logic
            '''
            my_fix = flight.fixes[i]
            next_fix = flight.fixes[i + 1]
            result.last_time = my_fix.rawtime
            alt = next_fix.gnss_alt if alt_source == 'GPS' else next_fix.press_alt

            if alt > max_altitude:
                max_altitude = alt

            '''handle stopped task'''
            if task.stopped_time and next_fix.rawtime > deadline:
                result.last_altitude = alt  # check the rules on this point..which alt to
                break

            '''check if pilot has arrived in goal (last turnpoint) so we can stop.'''
            if t >= len(task.turnpoints):
                break

            '''check if task deadline has passed'''
            if task.task_deadline < next_fix.rawtime:
                # Task has ended
                result.last_altitude = alt
                break

            '''check if start closing time passed and pilot did not start'''
            if task.start_close_time and task.start_close_time < my_fix.rawtime and not started:
                # start closed
                break

            '''check tp type is known'''
            if task.turnpoints[t].type not in ('launch', 'speed', 'waypoint', 'endspeed', 'goal'):
                assert False, "Unknown turnpoint type: %s" % task.turnpoints[t].type

            '''launch turnpoint managing'''
            if task.turnpoints[t].type == "launch":
                # not checking launch yet
                if task.check_launch == 'on':
                    # Set radius to check to 200m (in the task def it will be 0)
                    # could set this in the DB or even formula if needed..???
                    task.turnpoints[t].radius = 200  # meters
                    if task.turnpoints[t].in_radius(my_fix, tolerance, min_tol_m):
                        result.waypoints_achieved.append(
                            ["Left Launch", my_fix.rawtime, alt])  # pilot has achieved turnpoint
                        t += 1

                else:
                    t += 1

            # to do check for restarts for elapsed time tasks and those that allow jump the gun
            # if started and task.task_type != 'race' or result.jump_the_gun is not None:

            '''start turnpoint managing'''
            '''given all n crossings for a turnpoint cylinder, sorted in ascending order by their crossing time,
            the time when the cylinder was reached is determined.
            turnpoint[i] = SSS : reachingTime[i] = crossing[n].time
            turnpoint[i] =? SSS : reachingTime[i] = crossing[0].time

            We need to check start in 3 cases:
            - pilot has not started yet
            - race has multiple starts
            - task is elapsed time
            '''

            if (((task.turnpoints[t].type == "speed" and not started)
                 or
                 (task.turnpoints[t - 1].type == "speed" and (task.SS_interval or task.task_type == 'ELAPSED TIME')))
                    and
                    (my_fix.rawtime >= (task.start_time - max_jump_the_gun))
                    and
                    (not task.start_close_time or my_fix.rawtime <= task.start_close_time)):

                # we need to check if it is a restart, so to use correct tp
                if task.turnpoints[t - 1].type == "speed":
                    SS_tp = task.turnpoints[t - 1]
                    restarting = True
                else:
                    SS_tp = task.turnpoints[t]
                    restarting = False

                if start_made_civl(my_fix, next_fix, SS_tp, tolerance, min_tol_m):
                    time = round(tp_time_civl(my_fix, next_fix, SS_tp), 0)
                    result.waypoints_achieved.append(["SSS", time, alt])  # pilot has started

                    started = True
                    result.fixed_LC = 0  # resetting LC to last start time
                    if not restarting:
                        t += 1

            if started:
                '''Turnpoint managing'''
                if (task.turnpoints[t].shape == 'circle'
                        and task.turnpoints[t].type in ('endspeed', 'waypoint')):
                    tp = task.turnpoints[t]
                    if tp_made_civl(my_fix, next_fix, tp, tolerance, min_tol_m):
                        time = round(tp_time_civl(my_fix, next_fix, tp), 0)
                        name = 'ESS' if tp.type == 'endspeed' else 'TP{:02}'.format(waypoint)
                        # if tp.type == 'endspeed' and ess_altitude == 0:
                        #     ess_altitude = alt
                        # result.best_waypoint_achieved = 'waypoint ' + str(waypoint) + ' made'
                        result.waypoints_achieved.append([name, time, alt])  # pilot has achieved turnpoint
                        waypoint += 1
                        t += 1

                if task.turnpoints[t].type == 'goal':
                    goal_tp = task.turnpoints[t]
                    if ((goal_tp.shape == 'circle' and tp_made_civl(my_fix, next_fix, goal_tp, tolerance, min_tol_m))
                            or (goal_tp.shape == 'line' and (in_semicircle(task, task.turnpoints, t, my_fix)
                                                             or in_semicircle(task, task.turnpoints, t, next_fix)))):
                        result.waypoints_achieved.append(
                            ['Goal', next_fix.rawtime, alt])  # pilot has achieved turnpoint
                        # if goal_altitude == 0:  goal_altitude = alt
                        break

            '''update result data
            Once launched, distance flown should be max result among:
            - previous value;
            - optimized dist. to last turnpoint made;
            - total optimized distance minus opt. distance from next wpt to goal minus dist. to next wpt;
            '''
            if t > 0:
                result.distance_flown = max(result.distance_flown, (distances2go[0] - distances2go[t - 1]),
                                            distance_flown(next_fix, t, task.optimised_turnpoints, task.turnpoints[t],
                                                           distances2go))
            # print('fix {} | Dist. flown {} | tp {}'.format(i, round(result.distance_flown, 2), t))

            '''Leading coefficient
                LC = taskTime(i)*(bestDistToESS(i-1)^2 - bestDistToESS(i)^2 )
                i : i ? TrackPoints In SS'''
            if started and not any(e[0] == 'ESS' for e in result.waypoints_achieved):
                real_start_time = max([e[1] for e in result.waypoints_achieved if e[0] == 'SSS'])
                taskTime = next_fix.rawtime - real_start_time
                best_dist_to_ess.append(task.opt_dist_to_ESS - result.distance_flown)
                result.fixed_LC += lib.coef_func(taskTime, best_dist_to_ess[0], best_dist_to_ess[1])
                best_dist_to_ess.pop(0)

        '''final results'''
        result.max_altitude = max_altitude
        result.landing_time = flight.landing_fix.rawtime
        result.landing_altitude = flight.landing_fix.gnss_alt if alt_source == 'GPS' else flight.landing_fix.press_alt

        if started:
            '''
            start time
            if race, the first times
            if multistart, the first time of the last gate pilot made
            if elapsed time, the time of last fix on start
            SS Time: the gate time'''
            result.SSS_time = task.start_time
            result.real_start_time = min([e[1] for e in result.waypoints_achieved if e[0] == 'SSS'])

            if task.task_type == 'RACE' and task.SS_interval:
                start_num = int((task.start_close_time - task.start_time) / task.SS_interval)
                gate = task.start_time + (task.SS_interval * start_num)  # last gate
                while gate > task.start_time:
                    if any([e for e in result.waypoints_achieved if e[0] == 'SSS' and e[1] >= gate]):
                        result.SSS_time = gate
                        result.real_start_time = min(
                            [e[1] for e in result.waypoints_achieved if e[0] == 'SSS' and e[1] >= gate])
                        break
                    gate -= task.SS_interval

            elif task.task_type == 'ELAPSED TIME':
                result.real_start_time = max([e[1] for e in result.waypoints_achieved if e[0] == 'SSS'])
                result.SSS_time = result.real_start_time

            # result.Start_time_str = (("%02d:%02d:%02d") % rawtime_float_to_hms(result.SSS_time + time_offset))

            '''ESS Time'''
            if any(e[0] == 'ESS' for e in result.waypoints_achieved):
                # result.ESS_time, ess_altitude = min([e[1] for e in result.waypoints_achieved if e[0] == 'ESS'])
                result.ESS_time, result.ESS_altitude = min(
                    [(x[1], x[2]) for x in result.waypoints_achieved if x[0] == 'ESS'], key=lambda t: t[0])
                result.speed = (task.SS_distance / 1000) / (result.ss_time / 3600)
                # result.ESS_time_str = (("%02d:%02d:%02d") % rawtime_float_to_hms(result.ESS_time + time_offset))
                # result.ss_time = result.ESS_time - result.SSS_time
                # result.ss_time_str = (("%02d:%02d:%02d") % rawtime_float_to_hms(result.ESS_time - result.SSS_time))

                '''Distance flown'''
                ''' ?p:p?PilotsLandingBeforeGoal:bestDistancep = max(minimumDistance, taskDistance-min(?trackp.pointi shortestDistanceToGoal(trackp.pointi)))
                    ?p:p?PilotsReachingGoal:bestDistancep = taskDistance
                '''
                if any(e[0] == 'Goal' for e in result.waypoints_achieved):
                    result.distance_flown = distances2go[0]
                    # result.goal_time = min([e[1] for e in result.waypoints_achieved if e[0] == 'Goal'])
                    result.goal_time, result.goal_altitude = min(
                        [(x[1], x[2]) for x in result.waypoints_achieved if x[0] == 'Goal'], key=lambda t: t[0])
                    result.result_type = 'goal'

        result.best_waypoint_achieved = str(result.waypoints_achieved[-1][0]) if result.waypoints_achieved else None

        # if result.ESS_time is None: # we need to do this after other operations
        # result.fixed_LC += formula_parameters.coef_landout((task.task_deadline - task.start_time),
        # ((task.opt_dist_to_ESS - result.distance_flown) / 1000))
        # print('    * Did not reach ESS LC: {}'.format(result.fixed_LC))

        result.fixed_LC = lib.coef_scaled(result.fixed_LC, task.opt_dist_to_ESS)
        # print('    * Final LC: {} \n'.format(result.fixed_LC))
        return result

    def to_db(self, task_id, track_id=None, session=None):
        """ stores new calculated results to db
            if track_id is not given, it inserts a new result
            else it updates existing one """
        from collections import Counter
        from db_tables import tblTaskResult as R, tblParticipant as P, tblTask as T
        from sqlalchemy import and_, or_
        from sqlalchemy.exc import SQLAlchemyError

        '''checks conformity'''
        if not self.goal_time:
            self.goal_time = 0
        endss = 0 if self.ESS_time is None else self.ESS_time
        num_wpts = len(Counter(el[0] for el in self.waypoints_achieved))

        '''database connection'''
        with Database(session) as db:
            if self.par_id is None:
                '''we have a result without pilot id. Try with ID number'''
                if self.ID is None:
                    '''we don't have any info about pilot'''
                    return None
                try:
                    comp_id = db.session.query(T).get(task_id).comPk
                    self.par_id = db.session.query(P.parPk).filter(
                        and_(P.parID == self.ID, P.comPk == comp_id)).scalar()
                except SQLAlchemyError:
                    print('Get registered pilot error')
                    db.session.rollback()
                if self.par_id is None:
                    '''we did not find a registered pilot for the result'''
                    return None

            if track_id:
                results = db.session.query(R)
                r = results.get(track_id)
            else:
                '''create a new result'''
                r = R(parPk=self.par_id, tasPk=task_id)

            r.tarDistance = self.distance_flown
            r.tarSpeed = self.speed
            r.tarLaunch = self.first_time
            r.tarStart = self.real_start_time
            r.tarGoal = self.goal_time
            r.tarSS = self.SSS_time
            r.tarES = endss
            r.tarSpeed = self.speed
            r.tarTurnpoints = num_wpts
            r.tarFixedLC = self.fixed_LC
            r.tarESAltitude = self.ESS_altitude
            r.tarGoalAltitude = self.goal_altitude
            r.tarMaxAltitude = self.max_altitude
            r.tarLastAltitude = self.last_altitude
            r.tarLastTime = self.last_time
            r.tarLandingAltitude = self.landing_altitude
            r.tarLandingTime = self.landing_time
            r.tarResultType = self.result_type
            r.tarComment = self.comment
            r.traFile = self.track_file

            if not track_id:
                db.session.add(r)
            db.session.flush()

    def to_geojson_result(self, track, task, second_interval=5):
        """Dumps the flight to geojson format used for mapping.
        Contains tracklog split into pre SSS, pre Goal and post goal parts, thermals, takeoff/landing,
        result object, waypoints achieved, and bounds

        second_interval = resolution of tracklog. default one point every 5 seconds. regardless it will
                            keep points where waypoints were achieved.
        returns the Json string."""

        from geojson import Point, Feature, FeatureCollection, MultiLineString
        from route import distance
        from collections import namedtuple

        features = []
        toff_land = []
        thermals = []
        point = namedtuple('fix', 'lat lon')

        min_lat = track.flight.fixes[0].lat
        min_lon = track.flight.fixes[0].lon
        max_lat = track.flight.fixes[0].lat
        max_lon = track.flight.fixes[0].lon
        bbox = [[min_lat, min_lon], [max_lat, max_lon]]

        takeoff = Point((track.flight.takeoff_fix.lon, track.flight.takeoff_fix.lat))
        toff_land.append(Feature(geometry=takeoff, properties={"TakeOff": "TakeOff"}))
        landing = Point((track.flight.landing_fix.lon, track.flight.landing_fix.lat))
        toff_land.append(Feature(geometry=landing, properties={"Landing": "Landing"}))

        for thermal in track.flight.thermals:
            thermals.append((thermal.enter_fix.lon, thermal.enter_fix.lat,
                             f'{thermal.vertical_velocity():.1f}m/s gain:{thermal.alt_change():.0f}m'))

        pre_sss = []
        pre_goal = []
        post_goal = []
        waypoint_achieved = []

        # if the pilot did not make goal, goal time will be None. set to after end of track to avoid issues.
        if not self.goal_time:
            goal_time = track.flight.fixes[-1].rawtime + 1
        else:
            goal_time = self.goal_time

        # if the pilot did not make SSS then it will be 0, set to task start time.
        if self.SSS_time == 0:
            SSS_time = task.start_time
        else:
            SSS_time = self.SSS_time

        waypoint = 0
        lastfix = track.flight.fixes[0]
        for fix in track.flight.fixes:
            bbox = checkbbox(fix.lat, fix.lon, bbox)
            keep = False
            if fix.rawtime >= lastfix.rawtime + second_interval:
                keep = True
                lastfix = fix

            if fix.rawtime == self.waypoints_achieved[waypoint][1]:
                time = ("%02d:%02d:%02d" % rawtime_float_to_hms(fix.rawtime + task.time_offset * 3600))
                waypoint_achieved.append(
                    [fix.lon, fix.lat, fix.gnss_alt, fix.press_alt, self.waypoints_achieved[waypoint][0], time,
                     fix.rawtime,
                     f'{self.waypoints_achieved[waypoint][0]} '
                     f'gps alt: {fix.gnss_alt:.0f}m '
                     f'baro alt: {fix.press_alt:.0f}m '
                     f'time: {time}'])
                keep = True
                if waypoint < len(self.waypoints_achieved) - 1:
                    waypoint += 1

            if keep:
                if fix.rawtime <= SSS_time:
                    pre_sss.append((fix.lon, fix.lat, fix.gnss_alt, fix.press_alt))
                if SSS_time <= fix.rawtime <= goal_time:
                    pre_goal.append((fix.lon, fix.lat, fix.gnss_alt, fix.press_alt))
                if fix.rawtime >= goal_time:
                    post_goal.append((fix.lon, fix.lat, fix.gnss_alt, fix.press_alt))

        for w in range(1, len(waypoint_achieved[1:]) + 1):
            current = point(lon=waypoint_achieved[w][0], lat=waypoint_achieved[w][1])
            previous = point(lon=waypoint_achieved[w - 1][0], lat=waypoint_achieved[w - 1][1])
            straight_line_dist = distance(previous, current) / 1000
            time_taken = (waypoint_achieved[w][6] - waypoint_achieved[w - 1][6]) / 3600
            time_takenHMS = rawtime_float_to_hms(time_taken * 3600)
            speed = straight_line_dist / time_taken
            waypoint_achieved[w].append(round(straight_line_dist, 2))
            waypoint_achieved[w].append("%02d:%02d:%02d" % time_takenHMS)
            waypoint_achieved[w].append(round(speed, 2))

        waypoint_achieved[0].append(0)
        waypoint_achieved[0].append("0:00:00")
        waypoint_achieved[0].append('-')

        route_multilinestring = MultiLineString([pre_sss])
        features.append(Feature(geometry=route_multilinestring, properties={"Track": "Pre_SSS"}))
        route_multilinestring = MultiLineString([pre_goal])
        features.append(Feature(geometry=route_multilinestring, properties={"Track": "Pre_Goal"}))
        route_multilinestring = MultiLineString([post_goal])
        features.append(Feature(geometry=route_multilinestring, properties={"Track": "Post_Goal"}))

        feature_collection = FeatureCollection(features)

        data = {'tracklog': feature_collection, 'thermals': thermals, 'takeoff_landing': toff_land,
                'result': jsonpickle.dumps(self), 'bounds': bbox, 'waypoint_achieved': waypoint_achieved}

        return data

    def save_result_file(self, data, trackid):
        """save result file in the correct folder as defined by DEFINES"""

        from os import path, makedirs
        import Defines
        res_path = Defines.MAPOBJDIR + 'tracks/'

        """check if directory already exists"""
        if not path.isdir(res_path):
            makedirs(res_path)
        """creates a name for the track
        name_surname_date_time_index.igc
        if we use flight date then we need an index for multiple tracks"""

        filename = 'result_' + str(trackid) + '.json'
        fullname = path.join(res_path, filename)
        """copy file"""
        try:
            with open(fullname, 'w') as f:
                json.dump(data, f)
            return fullname
        except:
            print('Error saving file:', fullname)


def adjust_flight_results(task, lib):
    """ Called when multi-start or elapsed time task was stopped.
        We need to check again and adjust results of pilots that flew more than task duration"""
    maxtime = task.duration
    for pilot in task.pilots:
        if pilot.last_fix_time - pilot.SSS_time > maxtime:
            flight = pilot.track.flight
            last_time = pilot.result.SSS_time + maxtime
            pilot.result = Flight_result.check_flight(flight, task, lib, 5, deadline=last_time)


def verify_all_tracks(task, lib):
    """ Gets in input:
            task:       Task object
            lib:        Formula library module"""
    from os import path

    print('getting tracks...')
    for pilot in task.pilots:
        if pilot.result_type not in ('abs', 'dnf', 'mindist'):
            print(f"{pilot.ID}. {pilot.name}: ({pilot.track.filename})")
            file_path = path.join(task.file_path, pilot.track.filename)
            pilot.track.flight.create_from_file(file_path)
            if pilot.track.flight:
                pilot.result = Flight_result.check_flight(pilot.track.flight, task, lib, 5)
                print(f'   Goal: {bool(pilot.result.goal_time)} | part. LC: {pilot.result.fixed_LC}')


def update_all_results(results):
    """get results to update from the list"""
    from db_tables import tblTaskResult as R
    from sqlalchemy.exc import SQLAlchemyError

    mappings = []
    for pilot in results:
        res = pilot.result
        track_id = pilot.track_id

        '''checks conformity'''
        if not res.goal_time:
            res.goal_time = 0
        if not res.ESS_time:
            res.ESS_time = 0

        mapping = {'tarPk': track_id,
                   'tarDistance': res.distance_flown,
                   'tarSpeed': res.speed,
                   'tarLaunch': res.first_time,
                   'tarStart': res.real_start_time,
                   'tarGoal': res.goal_time,
                   'tarSS': res.SSS_time,
                   'tarES': res.ESS_time,
                   'tarTurnpoints': res.waypoints_made,
                   'tarFixedLC': res.fixed_LC,
                   'tarESAltitude': res.ESS_altitude,
                   'tarGoalAltitude': res.goal_altitude,
                   'tarMaxAltitude': res.max_altitude,
                   'tarLastAltitude': res.last_altitude,
                   'tarLastTime': res.last_time,
                   'tarLandingAltitude': res.landing_altitude,
                   'tarLandingTime': res.landing_time,
                   'tarResultType': res.result_type}
        mappings.append(mapping)

    '''update database'''
    with Database() as db:
        try:
            db.session.bulk_update_mappings(R, mappings)
            db.session.commit()
        except SQLAlchemyError:
            print(f'update all results on database gave an error')
            db.session.rollback()
            return False

    return True
