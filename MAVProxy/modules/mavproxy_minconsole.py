"""
  MAVProxy minimal console

  A minimal version of the console module with reduced fields
"""

import os, sys, math, time, re
import traceback

from MAVProxy.modules.lib import wxconsole
from MAVProxy.modules.lib import textconsole
from pymavlink import mavutil
from MAVProxy.modules.lib import mp_util
from MAVProxy.modules.lib import mp_module
from MAVProxy.modules.lib import mp_settings
from MAVProxy.modules.lib import wxsettings
from MAVProxy.modules.lib.mp_menu import *

green = (0, 128, 0)

class DisplayItem:
    def __init__(self, fmt, expression, row):
        self.expression = expression.strip('"\'')
        self.format = fmt.strip('"\'')
        re_caps = re.compile('[A-Z_][A-Z0-9_]+')
        self.msg_types = set(re.findall(re_caps, expression))
        self.row = row

class MinMinConsoleModule(mp_module.MPModule):
    def __init__(self, mpstate):
        super(MinMinConsoleModule, self).__init__(mpstate, "minconsole", "Minimal GUI console", public=True, multi_vehicle=True)
        self.in_air = False
        self.start_time = 0.0
        self.total_time = 0.0
        self.speed = 0
        self.max_link_num = 0
        self.last_sys_status_health = 0
        self.last_sys_status_errors_announce = 0
        self.user_added = {}
        self.safety_on = False
        self.unload_check_interval = 5 # seconds
        self.last_unload_check_time = time.time()
        self.add_command('minconsole', self.cmd_console, "minimal console module", ['add','list','remove'])
        mpstate.console = wxconsole.MessageConsole(title='Console')

        # setup some default status information
        mpstate.console.set_status('Mode', 'Mode: UNKNOWN', row=0, fg='blue')
        mpstate.console.set_status('SYSID', 'SYSID: ', row=0, fg='blue')
        mpstate.console.set_status('ARM', 'ARM: ARM', fg='grey', row=0)
        mpstate.console.set_status('FLT TIME', 'FLT TIME: --', row=0)
        mpstate.console.set_status('GPS', 'GPS: (--)', fg='red', row=2)
        mpstate.console.set_status('GPS2', 'GPS2: (--) ', fg='red', row=2)
        mpstate.console.set_status('VCC', 'VCC: --', fg='red', row=3)
        mpstate.console.set_status('AMP', 'AMP: --', fg='green', row=3)
        mpstate.console.set_status('THR', 'THR: ---', row=3)
        mpstate.console.set_status('ROLL', 'ROLL: ---', row=3)
        mpstate.console.set_status('PITCH', 'PITCH: ---', row=3)
        mpstate.console.set_status('YAW', 'YAW: ---', row=3)

        self.console_settings = mp_settings.MPSettings([
            ('debug_level', int, 0),
        ])

        self.vehicle_list = []
        self.vehicle_heartbeats = {}  # map from (sysid,compid) tuple to most recent HEARTBEAT nessage
        self.vehicle_menu = None
        self.vehicle_name_by_sysid = {}
        self.component_name = {}
        self.last_param_sysid_timestamp = None
        self.flight_information = {}

        # create the main menu
        if mp_util.has_wxpython:
            self.menu = MPMenuTop([])
            self.add_menu(MPMenuSubMenu('MAVProxy',
                                        items=[MPMenuItem('Settings', 'Settings', 'menuSettings'),
                                               MPMenuItem('Show Map', 'Load Map', '# module load map'),
                                               MPMenuItem('Show HUD', 'Load HUD', '# module load horizon'),
                                               MPMenuItem('Show Checklist', 'Load Checklist', '# module load checklist')]))
            self.vehicle_menu = MPMenuSubMenu('Vehicle', items=[])
            self.add_menu(self.vehicle_menu)

        self.shown_agl = False

    def cmd_console(self, args):
        usage = 'usage: console <add|list|remove|menu|set>'
        if len(args) < 1:
            print(usage)
            return
        cmd = args[0]
        if cmd == 'add':
            if len(args) < 4:
                print("usage: console add ID FORMAT EXPRESSION <row>")
                return
            if len(args) > 4:
                row = int(args[4])
            else:
                row = 4
            self.user_added[args[1]] = DisplayItem(args[2], args[3], row)
            self.console.set_status(args[1], "", row=row)
        elif cmd == 'list':
            for k in sorted(self.user_added.keys()):
                d = self.user_added[k]
                print("%s : FMT=%s EXPR=%s ROW=%u" % (k, d.format, d.expression, d.row))
        elif cmd == 'remove':
            if len(args) < 2:
                print("usage: console remove ID")
                return
            id = args[1]
            if id in self.user_added:
                self.user_added.pop(id)
        elif cmd == 'menu':
            self.cmd_menu(args[1:])
        elif cmd == 'set':
            self.cmd_set(args[1:])
        else:
            print(usage)

    def add_menu(self, menu):
        '''add a new menu'''
        self.menu.add(menu)
        self.mpstate.console.set_menu(self.menu, self.menu_callback)

    def cmd_menu_add(self, args):
        '''add to console menus'''
        if len(args) < 2:
            print("Usage: console menu add MenuPath command")
            return
        menupath = args[0].strip('"').split(':')
        name = menupath[-1]
        cmd = '# ' + ' '.join(args[1:])
        self.menu.add_to_submenu(menupath[:-1], MPMenuItem(name, name, cmd))
        self.mpstate.console.set_menu(self.menu, self.menu_callback)

    def cmd_menu(self, args):
        '''control console menus'''
        if len(args) < 2:
            print("Usage: console menu <add>")
            return
        if args[0] == 'add':
            self.cmd_menu_add(args[1:])

    def cmd_set(self, args):
        '''set console options'''
        self.console_settings.command(args)

    def remove_menu(self, menu):
        '''add a new menu'''
        self.menu.remove(menu)
        self.mpstate.console.set_menu(self.menu, self.menu_callback)

    def unload(self):
        '''unload module'''
        self.mpstate.console.close()
        self.mpstate.console = textconsole.SimpleConsole()

    def menu_callback(self, m):
        '''called on menu selection'''
        if m.returnkey.startswith('# '):
            cmd = m.returnkey[2:]
            if m.handler is not None:
                if m.handler_result is None:
                    return
                cmd += m.handler_result
            self.mpstate.functions.process_stdin(cmd)
        if m.returnkey == 'menuSettings':
            wxsettings.WXSettings(self.settings)


    def estimated_time_remaining(self, lat, lon, wpnum, speed):
        '''estimate time remaining in mission in seconds'''
        if self.module('wp') is None:
            return 0
        idx = wpnum
        if wpnum >= self.module('wp').wploader.count():
            return 0
        distance = 0
        done = set()
        while idx < self.module('wp').wploader.count():
            if idx in done:
                break
            done.add(idx)
            w = self.module('wp').wploader.wp(idx)
            if w.command == mavutil.mavlink.MAV_CMD_DO_JUMP:
                idx = int(w.param1)
                continue
            idx += 1
            if (w.x != 0 or w.y != 0) and w.command in [mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                                                        mavutil.mavlink.MAV_CMD_NAV_LOITER_UNLIM,
                                                        mavutil.mavlink.MAV_CMD_NAV_LOITER_TURNS,
                                                        mavutil.mavlink.MAV_CMD_NAV_LOITER_TIME,
                                                        mavutil.mavlink.MAV_CMD_NAV_LAND,
                                                        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF]:
                distance += mp_util.gps_distance(lat, lon, w.x, w.y)
                lat = w.x
                lon = w.y
                if w.command == mavutil.mavlink.MAV_CMD_NAV_LAND:
                    break
        return distance / speed

    def vehicle_type_string(self, hb):
        '''return vehicle type string from a heartbeat'''
        if hb.type in [mavutil.mavlink.MAV_TYPE_FIXED_WING,
                            mavutil.mavlink.MAV_TYPE_VTOL_DUOROTOR,
                            mavutil.mavlink.MAV_TYPE_VTOL_QUADROTOR,
                            mavutil.mavlink.MAV_TYPE_VTOL_TILTROTOR]:
            return 'Plane'
        if hb.type == mavutil.mavlink.MAV_TYPE_GROUND_ROVER:
            return 'Rover'
        if hb.type == mavutil.mavlink.MAV_TYPE_SURFACE_BOAT:
            return 'Boat'
        if hb.type == mavutil.mavlink.MAV_TYPE_SUBMARINE:
            return 'Sub'
        if hb.type in [mavutil.mavlink.MAV_TYPE_QUADROTOR,
                           mavutil.mavlink.MAV_TYPE_COAXIAL,
                           mavutil.mavlink.MAV_TYPE_HEXAROTOR,
                           mavutil.mavlink.MAV_TYPE_OCTOROTOR,
                           mavutil.mavlink.MAV_TYPE_TRICOPTER,
                           mavutil.mavlink.MAV_TYPE_DODECAROTOR]:
            return "Copter"
        if hb.type == mavutil.mavlink.MAV_TYPE_HELICOPTER:
            return "Heli"
        if hb.type == mavutil.mavlink.MAV_TYPE_ANTENNA_TRACKER:
            return "Tracker"
        if hb.type == mavutil.mavlink.MAV_TYPE_AIRSHIP:
            return "Blimp"
        elif hb.type == mavutil.mavlink.MAV_TYPE_ADSB:
            return "ADSB"
        elif hb.type == mavutil.mavlink.MAV_TYPE_ODID:
            return "ODID"
        return "UNKNOWN(%u)" % hb.type

    def component_type_string(self, hb):
        # note that we rely on vehicle_type_string for basic vehicle types
        if hb.type == mavutil.mavlink.MAV_TYPE_GCS:
            return "GCS"
        elif hb.type == mavutil.mavlink.MAV_TYPE_GIMBAL:
            return "Gimbal"
        elif hb.type == mavutil.mavlink.MAV_TYPE_ONBOARD_CONTROLLER:
            return "CC"
        elif hb.type == mavutil.mavlink.MAV_TYPE_ADSB:
            return "ADSB"
        elif hb.type == mavutil.mavlink.MAV_TYPE_ODID:
            return "ODID"
        elif hb.type == mavutil.mavlink.MAV_TYPE_GENERIC:
            return "Generic"
        return self.vehicle_type_string(hb)

    def update_vehicle_menu(self):
        '''update menu for new vehicles'''
        self.vehicle_menu.items = []
        for s in sorted(self.vehicle_list):
            clist = self.module('param').get_component_id_list(s)
            if len(clist) == 1:
                name = 'SysID %u: %s' % (s, self.vehicle_name_by_sysid[s])
                self.vehicle_menu.items.append(MPMenuItem(name, name, '# vehicle %u' % s))
            else:
                for c in sorted(clist):
                    try:
                        name = 'SysID %u[%u]: %s' % (s, c, self.component_name[s][c])
                    except KeyError as e:
                        name = 'SysID %u[%u]: ?' % (s,c)
                    self.vehicle_menu.items.append(MPMenuItem(name, name, '# vehicle %u:%u' % (s,c)))
        self.mpstate.console.set_menu(self.menu, self.menu_callback)
    
    def add_new_vehicle(self, hb):
        '''add a new vehicle'''
        if hb.type == mavutil.mavlink.MAV_TYPE_GCS:
            return
        sysid = hb.get_srcSystem()
        self.vehicle_list.append(sysid)
        self.vehicle_name_by_sysid[sysid] = self.vehicle_type_string(hb)
        self.update_vehicle_menu()

    def check_critical_error(self, msg):
        '''check for any error bits being set in SYS_STATUS'''
        sysid = msg.get_srcSystem()
        compid = msg.get_srcComponent()
        hb = self.vehicle_heartbeats.get((sysid, compid), None)
        if hb is None:
            return
        # only ArduPilot populates the fields with internal error stuff:
        if hb.autopilot != mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA:
            return

        errors = msg.errors_count1 | (msg.errors_count2<<16)
        if errors == 0:
            return
        now = time.time()
        if now - self.last_sys_status_errors_announce > self.mpstate.settings.sys_status_error_warn_interval:
            self.last_sys_status_errors_announce = now
            self.say("Critical failure 0x%x sysid=%u compid=%u" % (errors, sysid, compid))

    def set_component_name(self, sysid, compid, name):
        if sysid not in self.component_name:
            self.component_name[sysid] = {}
        if compid not in self.component_name[sysid]:
            self.component_name[sysid][compid] = name
            self.update_vehicle_menu()

    # this method is called when a HEARTBEAT arrives from any source:
    def handle_heartbeat_anysource(self, msg):
            sysid = msg.get_srcSystem()
            compid = msg.get_srcComponent()
            type = msg.get_type()
            if type == 'HEARTBEAT':
                self.vehicle_heartbeats[(sysid, compid)] = msg
            if not sysid in self.vehicle_list:
                self.add_new_vehicle(msg)
            self.set_component_name(sysid, compid, self.component_type_string(msg))

    # this method is called when a GIMBAL_DEVICE_INFORMATION arrives
    # from any source:
    def handle_gimbal_device_information_anysource(self, msg):
            sysid = msg.get_srcSystem()
            compid = msg.get_srcComponent()
            self.set_component_name(sysid, compid, "%s-%s" %
                                    (msg.vendor_name, msg.model_name))

    def handle_gps_raw(self, msg):
            master = self.master
            type = msg.get_type()
            if type == 'GPS_RAW_INT':
                field = 'GPS'
                prefix = 'GPS'
            else:
                field = 'GPS2'
                prefix = 'GPS2'
            nsats = msg.satellites_visible
            fix_type = msg.fix_type
            if fix_type >= 3:
                self.console.set_status(field, '%s: (%u)' % (prefix, nsats), fg=green, row=2)
            else:
                self.console.set_status(field, '%s: (%u)' % (prefix, nsats), fg='red', row=2)
            if type == 'GPS_RAW_INT':
                vfr_hud_heading = master.field('VFR_HUD', 'heading', None)
                if vfr_hud_heading is None:
                    # try to fill it in from GLOBAL_POSITION_INT instead:
                    vfr_hud_heading = master.field('GLOBAL_POSITION_INT', 'hdg', None)
                    if vfr_hud_heading is not None:
                        if vfr_hud_heading == 65535:  # mavlink magic "unknown" value
                            vfr_hud_heading = None
                        else:
                            vfr_hud_heading /= 100
                if vfr_hud_heading is None:
                    vfr_hud_heading = '---'
                else:
                    vfr_hud_heading = '%3u' % vfr_hud_heading
                self.console.set_status('HDG', 'HDG: %s' % vfr_hud_heading, row=2)

    def handle_vfr_hud(self, msg):
            master = self.master

            if master.mavlink10():
                alt = master.field('GPS_RAW_INT', 'alt', 0) / 1.0e3
            else:
                alt = master.field('GPS_RAW', 'alt', 0)
            home_lat = None
            home_lng = None
            if  self.module('wp') is not None:
                home = self.module('wp').get_home()
                if home is not None:
                    home_lat = home.x
                    home_lng = home.y

            lat = master.field('GLOBAL_POSITION_INT', 'lat', 0) * 1.0e-7
            lng = master.field('GLOBAL_POSITION_INT', 'lon', 0) * 1.0e-7
            rel_alt = master.field('GLOBAL_POSITION_INT', 'relative_alt', 0) * 1.0e-3
            vehicle_agl = master.field('TERRAIN_REPORT', 'current_height', None)
            if vehicle_agl is not None or self.shown_agl:
                self.shown_agl = True
                if vehicle_agl is None:
                    agl_display = '---'
                else:
                    agl_display = self.height_string(vehicle_agl)
                self.console.set_status('AGL', 'AGL: %s' % agl_display, row=1)
            self.console.set_status('ALT', 'ALT: %s' % self.height_string(rel_alt), row=1)
            self.console.set_status('ARSPD', 'ARSPD: %s' % self.speed_string(msg.airspeed), row=1)
            self.console.set_status('GNDSPD', 'GNDSPD: %s' % self.speed_string(msg.groundspeed), row=1)
            self.console.set_status('THR', 'THR: %u' % msg.throttle, row=3)

            sysid = msg.get_srcSystem()
            if (sysid not in self.flight_information or
                self.flight_information[sysid].supported != True):
                    self.update_flight_time_from_vfr_hud(msg)

    def update_flight_time_from_vfr_hud(self, msg):
            t = time.localtime(msg._timestamp)
            flying = False
            if self.mpstate.vehicle_type == 'copter':
                flying = self.master.motors_armed()
            else:
                flying = msg.groundspeed > 3
            if flying and not self.in_air:
                self.in_air = True
                self.start_time = time.mktime(t)
            elif flying and self.in_air:
                self.total_time = time.mktime(t) - self.start_time
                self.console.set_status('FLT TIME', 'FLT TIME %u:%02u' % (int(self.total_time)/60, int(self.total_time)%60))
            elif not flying and self.in_air:
                self.in_air = False
                self.total_time = time.mktime(t) - self.start_time
                self.console.set_status('FLT TIME', 'FLT TIME %u:%02u' % (int(self.total_time)/60, int(self.total_time)%60))

    def handle_attitude(self, msg):
            self.console.set_status('ROLL', 'ROLL: %u' % math.degrees(msg.roll), row=3)
            self.console.set_status('PITCH', 'PITCH: %u' % math.degrees(msg.pitch), row=3)
            self.console.set_status('YAW', 'YAW: %u' % math.degrees(msg.yaw), row=3)

    def handle_sys_status(self, msg):
            self.last_sys_status_health = msg.onboard_control_sensors_health

            if ((msg.onboard_control_sensors_enabled & mavutil.mavlink.MAV_SYS_STATUS_SENSOR_MOTOR_OUTPUTS) == 0):
                self.safety_on = True
            else:
                self.safety_on = False                

    def handle_power_status(self, msg):
            if msg.Vcc >= 4600 and msg.Vcc <= 5300:
                fg = green
            else:
                fg = 'red'
            self.console.set_status('VCC', 'VCC: %.2f' % (msg.Vcc * 0.001), fg=fg, row=3)

    def handle_battery_status(self, msg):
            # current_battery is in centi-amps, convert to amps
            if msg.current_battery != 65535:
                current = msg.current_battery / 100.0
                fg = green
                self.console.set_status('AMP', 'AMP: %.1f' % current, fg=fg, row=3)
            else:
                self.console.set_status('AMP', 'AMP: --', fg='red', row=3)

    # this method is called on receipt of any HEARTBEAT so long as it
    # comes from the device we are interested in
    def handle_heartbeat(self, msg):
            sysid = msg.get_srcSystem()
            compid = msg.get_srcComponent()
            master = self.master

            fmode = master.flightmode
            if self.settings.vehicle_name:
                fmode = self.settings.vehicle_name + ':' + fmode
            self.console.set_status('Mode', '%s' % fmode, fg='blue')
            if len(self.vehicle_list) > 1:
                self.console.set_status('SYSID', 'SYSID:%u' % sysid, fg='blue')
            if self.master.motors_armed():
                arm_colour = green
            else:
                arm_colour = 'red'
            armstring = 'ARM'
            # add safety switch state
            if self.safety_on:
                armstring += '(SAFE)'
            self.console.set_status('ARM', armstring, fg=arm_colour)
            if self.max_link_num != len(self.mpstate.mav_master):
                for i in range(self.max_link_num):
                    self.console.set_status('LINK%u'%(i+1), '', row=4)
                self.max_link_num = len(self.mpstate.mav_master)
            for m in self.mpstate.mav_master:
                if self.mpstate.settings.checkdelay:
                    highest_msec_key = (sysid, compid)
                    linkdelay = (self.mpstate.status.highest_msec.get(highest_msec_key, 0) - m.highest_msec.get(highest_msec_key,0))*1.0e-3
                else:
                    linkdelay = 0
                linkline = "LINK %s " % (self.link_label(m))
                fg = 'dark green'
                if m.linkerror:
                    linkline += "down"
                    fg = 'red'
                else:
                    packets_rcvd_percentage = 100
                    if (m.mav_count+m.mav_loss) != 0: #avoid divide-by-zero
                        packets_rcvd_percentage = (100.0 * m.mav_count) / (m.mav_count + m.mav_loss)

                    linkbits = ["%u pkts" % m.mav_count,
                                "%u lost" % m.mav_loss,
                                "%.2fs delay" % linkdelay,
                    ]
                    try:
                        if m.mav.signing.sig_count:
                            # other end is sending us signed packets
                            if not m.mav.signing.secret_key:
                                # we've received signed packets but
                                # can't verify them
                                fg = 'orange'
                                linkbits.append("!KEY")
                            elif not m.mav.signing.sign_outgoing:
                                # we've received signed packets but aren't
                                # signing outselves; this can lead to hairloss
                                fg = 'orange'
                                linkbits.append("!SIGNING")
                            if m.mav.signing.badsig_count:
                                fg = 'orange'
                                linkbits.append("%u badsigs" % m.mav.signing.badsig_count)
                    except AttributeError as e:
                        # mav.signing.sig_count probably doesn't exist
                        pass

                    linkline += "OK"

                    if linkdelay > 1 and fg == 'dark green':
                        fg = 'orange'

                self.console.set_status('LINK%u'%m.linknum, linkline, row=4, fg=fg)

    def handle_mission_current(self, msg):
            master = self.master
            if self.module('wp') is not None:
                wpmax = self.module('wp').wploader.count()
            else:
                wpmax = 0
            if wpmax > 0:
                wpmax = "/%u" % wpmax
            else:
                wpmax = ""
            self.console.set_status('WP', 'WP: %u%s' % (msg.seq, wpmax), row=2)
            lat = master.field('GLOBAL_POSITION_INT', 'lat', 0) * 1.0e-7
            lng = master.field('GLOBAL_POSITION_INT', 'lon', 0) * 1.0e-7
            if lat != 0 and lng != 0:
                airspeed = master.field('VFR_HUD', 'airspeed', 30)
                if abs(airspeed - self.speed) > 5:
                    self.speed = airspeed
                else:
                    self.speed = 0.98*self.speed + 0.02*airspeed
    def handle_nav_controller_output(self, msg):
            self.console.set_status('BRG', 'BRG: %u' % msg.target_bearing, row=2)

    def handle_high_latency2(self, msg):
            # The -180 here for for consistency with NAV_CONTROLLER_OUTPUT (-180->180), whereas HIGH_LATENCY2 is (0->360)
            self.console.set_status('BRG', 'BRG: %u' % ((msg.target_heading * 2) - 180), row=2)
            self.console.set_status('ALT', 'ALT: %s' % self.height_string(msg.altitude - self.module('terrain').ElevationModel.GetElevation(msg.latitude / 1E7, msg.longitude / 1E7)), row=1)
            self.console.set_status('ARSPD', 'ARSPD: %s' % self.speed_string(msg.airspeed / 5), row=1)
            self.console.set_status('GNDSPD', 'GNDSPD: %s' % self.speed_string(msg.groundspeed / 5), row=1)
            self.console.set_status('THR', 'THR: %u' % msg.throttle, row=3)
            self.console.set_status('HDG', 'HDG: %s' % (msg.heading * 2), row=2)
            self.console.set_status('WP', 'WP: %u/--' % (msg.wp_num), row=2)
            
            gps_failed = ((msg.failure_flags & mavutil.mavlink.HL_FAILURE_FLAG_GPS) == mavutil.mavlink.HL_FAILURE_FLAG_GPS)
            if gps_failed:
                self.console.set_status('GPS', 'GPS FAILED', fg='red')
            else:
                self.console.set_status('GPS', 'GPS OK', fg=green)

    def handle_flight_information(self, msg):
        sysid = msg.get_srcSystem()
        if sysid not in self.flight_information:
            self.flight_information[sysid] = self.FlightInformation(sysid)
        self.flight_information[sysid].last_seen = time.time()

        # NOTE! the takeoff_time_utc field is misnamed in the XML!
        if msg.takeoff_time_utc == 0:
            # 0 is "landed", so don't update so we preserve the last
            # flight tiem in the display
            return
        total_time = (msg.time_boot_ms - msg.takeoff_time_utc*0.001) * 0.001
        self.console.set_status('FLT TIME', 'FLT TIME %u:%02u' % (int(total_time)/60, int(total_time)%60))

    def handle_command_ack(self, msg):
        sysid = msg.get_srcSystem()

        if msg.command != mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL:
            return

        if sysid not in self.flight_information:
            return

        fi = self.flight_information[sysid]

        if msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
            fi.supported = True
        elif msg.result in [mavutil.mavlink.MAV_RESULT_DENIED, mavutil.mavlink.MAV_RESULT_FAILED]:
            fi.supported = False

    # update user-added console entries; called after a mavlink packet
    # is received:
    def update_user_added_keys(self, msg):
        type = msg.get_type()
        for id in self.user_added.keys():
            if type in self.user_added[id].msg_types:
                d = self.user_added[id]
                try:
                    val = mavutil.evaluate_expression(d.expression, self.master.messages)
                    console_string = d.format % val
                except Exception as ex:
                    console_string = "????"
                    self.console.set_status(id, console_string, row = d.row)
                    if self.console_settings.debug_level > 0:
                        exc_type, exc_value, exc_traceback = sys.exc_info()
                        if self.mpstate.settings.moddebug > 3:
                            traceback.print_exception(
                                exc_type,
                                exc_value,
                                exc_traceback,
                                file=sys.stdout
                            )
                        elif self.mpstate.settings.moddebug > 1:
                            traceback.print_exception(exc_type, exc_value, exc_traceback,
                                                      limit=2, file=sys.stdout)
                        elif self.mpstate.settings.moddebug == 1:
                            print(ex)
                        print(f"{id} failed")
                self.console.set_status(id, console_string, row = d.row)

    def mavlink_packet(self, msg):
        '''handle an incoming mavlink packet'''
        if not isinstance(self.console, wxconsole.MessageConsole):
            return
        if not self.console.is_alive():
            self.mpstate.console = textconsole.SimpleConsole()
            return
        type = msg.get_type()

        if type in frozenset(['HEARTBEAT', 'HIGH_LATENCY2']):
            self.handle_heartbeat_anysource(msg)

        elif type == 'GIMBAL_DEVICE_INFORMATION':
            self.handle_gimbal_device_information_anysource(msg)

        if self.last_param_sysid_timestamp != self.module('param').new_sysid_timestamp:
            '''a new component ID has appeared for parameters'''
            self.last_param_sysid_timestamp = self.module('param').new_sysid_timestamp
            self.update_vehicle_menu()

        if type == 'SYS_STATUS':
            self.check_critical_error(msg)

        if not self.message_is_from_primary_vehicle(msg):
            # don't process msgs from other than primary vehicle, other than
            # updating vehicle list
            return

        # add some status fields
        if type in [ 'GPS_RAW_INT', 'GPS2_RAW' ]:
            self.handle_gps_raw(msg)

        elif type == 'VFR_HUD':
            self.handle_vfr_hud(msg)

        elif type == 'ATTITUDE':
            self.handle_attitude(msg)

        elif type in ['SYS_STATUS']:
            self.handle_sys_status(msg)

        elif type == 'POWER_STATUS':
            self.handle_power_status(msg)

        elif type in ['HEARTBEAT', 'HIGH_LATENCY2']:
            self.handle_heartbeat(msg)

        elif type in ['MISSION_CURRENT']:
            self.handle_mission_current(msg)

        elif type == 'NAV_CONTROLLER_OUTPUT':
            self.handle_nav_controller_output(msg)

        # note that we also process this as a HEARTBEAT message above!
        if type == 'HIGH_LATENCY2':
            self.handle_high_latency2(msg)

        elif type == 'FLIGHT_INFORMATION':
            self.handle_flight_information(msg)

        elif type == 'BATTERY_STATUS':
            self.handle_battery_status(msg)

        elif type == 'COMMAND_ACK':
            self.handle_command_ack(msg)

        self.update_user_added_keys(msg)

        # we've received a packet from the vehicle; probe for
        # FLIGHT_INFORMATION support:
        self.probe_for_flight_information(msg.get_srcSystem(), msg.get_srcComponent())

    class FlightInformation():
        def __init__(self, sysid):
            self.sysid = sysid
            self.supported = None  # don't know
            self.last_seen = None  # last time we saw FLIGHT_INFORMATION
            self.last_set_message_interval_sent = None  # last time we sent set-interval

    def probe_for_flight_information(self, sysid, compid):
        '''if we don't know if this vehicle supports flight information,
        request it'''
        if sysid not in self.flight_information:
            self.flight_information[sysid] = self.FlightInformation(sysid)

        fi = self.flight_information[sysid]

        now  = time.time()

        if fi.supported is not False and (fi.last_seen is None or now - fi.last_seen > 10):
            # if we stop getting FLIGHT_INFORMATION, re-request it:
            fi.supported = None

        if fi.supported is True or fi.supported is False:
            # we know one way or the other
            return

        # only probe once every 10 seconds
        if (fi.last_set_message_interval_sent is not None and
            now - fi.last_set_message_interval_sent < 10):
            return
        fi.last_set_message_interval_sent = now

        self.master.mav.command_long_send(
            sysid,
            compid,
            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
            0,  # confirmation
            mavutil.mavlink.MAVLINK_MSG_ID_FLIGHT_INFORMATION,  # msg id
            500000,  # interval - 2Hz
            0,  # p3
            0,  # p4
            0,  # p5
            0,  # p6
            0)  # p7

    def idle_task(self):
        now = time.time()
        if self.last_unload_check_time + self.unload_check_interval < now:
            self.last_unload_check_time = now
            if not self.console.is_alive():
                self.needs_unloading = True

def init(mpstate):
    '''initialise module'''
    return MinMinConsoleModule(mpstate)
