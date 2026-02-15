import sys
import json
import time
from pymavlink import mavutil
from pymavlink import mavwp
from MAVProxy.modules.lib import mp_module, mp_settings, mp_util
from MAVProxy.modules.mavproxy_rally import RallyModule
from MAVProxy.modules.mavproxy_mode import ModeModule
from MAVProxy.modules.lib import mission_item_protocol


def get_vehicle_name(vehtype):
    vehicle_names = {
        mavutil.mavlink.MAV_TYPE_FIXED_WING: 'Plane',
        mavutil.mavlink.MAV_TYPE_VTOL_DUOROTOR: 'Plane',
        mavutil.mavlink.MAV_TYPE_VTOL_QUADROTOR: 'Plane',
        mavutil.mavlink.MAV_TYPE_VTOL_TILTROTOR: 'Plane',
        mavutil.mavlink.MAV_TYPE_GROUND_ROVER: 'Rover',
        mavutil.mavlink.MAV_TYPE_SURFACE_BOAT: 'Boat',
        mavutil.mavlink.MAV_TYPE_SUBMARINE: 'Sub',
        mavutil.mavlink.MAV_TYPE_QUADROTOR: 'Copter',
        mavutil.mavlink.MAV_TYPE_COAXIAL: 'Copter',
        mavutil.mavlink.MAV_TYPE_HEXAROTOR: 'Copter',
        mavutil.mavlink.MAV_TYPE_OCTOROTOR: 'Copter',
        mavutil.mavlink.MAV_TYPE_TRICOPTER: 'Copter',
        mavutil.mavlink.MAV_TYPE_DODECAROTOR: 'Copter',
        mavutil.mavlink.MAV_TYPE_HELICOPTER: 'Heli',
        mavutil.mavlink.MAV_TYPE_ANTENNA_TRACKER: 'Tracker',
        mavutil.mavlink.MAV_TYPE_AIRSHIP: 'Blimp'
    }
    return vehicle_names.get(vehtype, f"UNKNOWN({vehtype})")

class SwarmModule(mission_item_protocol.MissionItemProtocolModule):
    def __init__(self, mpstate):
        super(SwarmModule, self).__init__(mpstate, "swarm", "swarm module", multi_vehicle=True, public=True)
        self.vehicleListing = []
        self.takeoffalt = 100  # Default takeoff altitude in meters
        self.separation_alt = 50  # Default separation altitude in meters
        self.vehicleLastHB = {}
        self.wploader_by_sysid = {}
        self.vehParamsToGet = []
        self.validVehicles = {
            mavutil.mavlink.MAV_TYPE_FIXED_WING,
            mavutil.mavlink.MAV_TYPE_VTOL_DUOROTOR,
            mavutil.mavlink.MAV_TYPE_VTOL_QUADROTOR,
            mavutil.mavlink.MAV_TYPE_VTOL_TILTROTOR,
            mavutil.mavlink.MAV_TYPE_GROUND_ROVER,
            mavutil.mavlink.MAV_TYPE_SURFACE_BOAT,
            mavutil.mavlink.MAV_TYPE_SUBMARINE,
            mavutil.mavlink.MAV_TYPE_QUADROTOR,
            mavutil.mavlink.MAV_TYPE_COAXIAL,
            mavutil.mavlink.MAV_TYPE_HEXAROTOR,
            mavutil.mavlink.MAV_TYPE_OCTOROTOR,
            mavutil.mavlink.MAV_TYPE_TRICOPTER,
            mavutil.mavlink.MAV_TYPE_HELICOPTER,
            mavutil.mavlink.MAV_TYPE_DODECAROTOR,
            mavutil.mavlink.MAV_TYPE_AIRSHIP
        }
        self.add_command('swarm', self.cmd_swarm, "swarm control", [
            "<status>", 
            "takeoff <separation_alt>", 
            "guided <lat> <lon> [<alt> <offset_z>]", 
            "rally <lat> <lon> [<alt> <offset_z>]", 
            "load <file_path>"
        ])
        global frame
        self.rally_module = RallyModule(mpstate)
        self.mode_module = ModeModule(mpstate)

    def command_name(a):
        '''command-line command name'''
        return a
    
    @staticmethod
    def loader_class():
        return mavwp.MissionItemProtocol_Rally
    
    def itemstype(self):
        '''returns description of items in the plural'''
        return 'rally items'

    def itemtype(self):
        '''returns description of item'''
        return 'rally item'
    
    def cmd_swarm(self, args):
        usage = "usage: swarm <status|takeoff <separation_alt>|guided <lat> <lon> [<alt> <offset_z>]|rally <lat> <lon> [<alt> <offset_z>]|load <file_path>>"
        if len(args) == 0:
            print(usage)
        elif args[0] == "status":
            self.print_status()
        elif args[0] == "takeoff" and len(args) == 2:
            try:
                self.separation_alt = int(args[1])
                self.set_takeoff_altitude()
            except ValueError:
                print("Invalid separation altitude. Please provide an integer value.")
        elif args[0] == "guided" and (len(args) == 3 or len(args) == 5):
            try:
                lat, lon = float(args[1]), float(args[2])
                alt = float(args[3]) if len(args) == 5 else None
                offset_z = float(args[4]) if len(args) == 5 else None
                self.send_guided_commands(lat, lon, alt, offset_z)
            except ValueError:
                print("Invalid guided command parameters. Please provide valid float values.")
        elif args[0] == "rally" and (len(args) == 3 or len(args) == 5):
            try:
                lat, lon = float(args[1]), float(args[2])
                alt = float(args[3]) if len(args) == 5 else None
                offset_z = float(args[4]) if len(args) == 5 else None
                self.send_rally_location(lat, lon, alt, offset_z)
            except ValueError:
                print("Invalid rally command parameters. Please provide valid float values.")
        elif args[0] == "load" and len(args) == 2:
            file_path = args[1]
            self.load_swarm_configuration(file_path)
        else:
            print(usage)

    def load_swarm_configuration(self, file_path):
        try:
            with open(file_path, 'r') as file:
                data = json.load(file)
                self.vehicleListing = []
                for veh in data["vehicles"]:
                    try:
                        sysid = int(veh["sysid"])
                        altitude = float(veh["altitude"])
                        self.vehicleListing.append((sysid, 1, 0, altitude))
                    except (ValueError, KeyError):
                        print(f"Invalid entry in configuration file: {veh}")
                self.config_loaded = True
            print("Swarm configuration loaded successfully.")
        except FileNotFoundError:
            print(f"Configuration file {file_path} not found.")
        except Exception as e:
            print(f"Error loading configuration file: {e}")

    def print_status(self):
        for veh in self.vehicleListing:
            sysid, compid, foll_sysid, veh_type = veh
            name = get_vehicle_name(veh_type)
            print(f"Vehicle {sysid}:{compid} - {name} (Leader: {foll_sysid})")

    def set_takeoff_altitude(self):
        for index, veh in enumerate(self.vehicleListing):
            sysid, compid, foll_sysid, veh_type = veh
            altitude = self.takeoffalt + index * self.separation_alt
            print(f"Setting takeoff altitude for Vehicle {sysid}:{compid} to {altitude} meters")
            self.mpstate.foreach_mav(sysid, compid, lambda mav: mav.command_int_send(
                sysid,
                compid,
                frame,
                mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                altitude
            ))

    def send_rally_location(self, lat, lon, alt=None, offset_z=None):
        if not self.config_loaded and (alt is None or offset_z is None):
            print("Configuration not loaded. Using provided altitude and offset.")
        for index, veh in enumerate(self.vehicleListing):
            sysid, compid, foll_sysid, altitude = veh
            command_lat = lat
            command_lon = lon
            if self.config_loaded:
                command_alt = altitude
            else:
                command_alt = alt + offset_z * index
            self.settings.target_system = sysid
            self.settings.target_component = compid
            #print(f"Sending rally command to Vehicle {sysid}:{compid} to LLA ({command_lat}, {command_lon}, {command_alt})")
            self.mpstate.foreach_mav(sysid, compid, lambda mav: self.rally_module.cmd_rally_add([command_alt]))
        
    def send_guided_commands(self, lat, lon, alt=None, offset_z=None):
        if not self.config_loaded and (alt is None or offset_z is None):
            print("Configuration not loaded. Using provided altitude and offset.")
        for index, veh in enumerate(self.vehicleListing):
            sysid, compid, foll_sysid, altitude = veh
            command_lat = lat
            command_lon = lon
            if self.config_loaded:
                command_alt = altitude
            else:
                command_alt = alt + offset_z * index
            self.settings.target_system = sysid
            self.settings.target_component = compid
            #print(f"Guided {sysid}:{compid} set to LLA ({command_lat}, {command_lon}, {command_alt})")
            self.mpstate.foreach_mav(sysid, compid, lambda mav: self.mode_module.cmd_guided([command_alt]))

    def mavlink_packet(self, m):
        mtype = m.get_type()
        sysid = m.get_srcSystem()
        compid = m.get_srcComponent()

        if mtype == 'HEARTBEAT' and m.type in self.validVehicles and not any(v[0] == sysid and v[1] == compid for v in self.vehicleListing):
            self.vehicleListing.append((sysid, compid, 0, m.type))
            self.vehParamsToGet.append((sysid, compid))
            self.needGUIupdate = True
            self.vehicleLastHB[(sysid, compid)] = time.time()
        elif (sysid, compid) in self.vehicleLastHB:
            if mtype == 'HEARTBEAT':
                self.vehicleLastHB[(sysid, compid)] = time.time()
            elif mtype == 'PARAM_VALUE' and m.param_id == "FOLL_SYSID":
                for i, veh in enumerate(self.vehicleListing):
                    if veh[0] == sysid and veh[1] == compid and veh[2] != int(m.param_value):
                        self.vehicleListing[i] = (veh[0], veh[1], int(m.param_value), veh[3])
                        self.needGUIupdate = True
                        break

def init(mpstate):
    return SwarmModule(mpstate)
