#!/usr/bin/env python3
'''
swarm module - Multi-vehicle guided control

Commands:
- swarm status               : Show all detected vehicles and their configured altitudes
- swarm alt <sysid> <alt>    : Set altitude for a vehicle (e.g., "swarm alt 1 50")
- swarm guided               : Send all configured vehicles to map click location
- swarm clear                : Clear all configured altitudes
'''

import time
from pymavlink import mavutil
from MAVProxy.modules.lib import mp_module


class SwarmModule(mp_module.MPModule):
    def __init__(self, mpstate):
        super(SwarmModule, self).__init__(mpstate, "swarm", "swarm module", multi_vehicle=True, public=True)
        
        self.vehicle_altitudes = {}  # {sysid: altitude}
        self.detected_vehicles = set()  # Set of sysids seen via heartbeat
        self.vehicle_last_hb = {}  # {sysid: last_heartbeat_time}
        
        self.valid_vehicles = {
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
        
        self.add_command('swarm', self.cmd_swarm, "swarm multi-vehicle control", [
            "status",
            "alt",
            "guided",
            "clear"
        ])

    def cmd_swarm(self, args):
        '''handle swarm commands'''
        if len(args) == 0:
            print("Usage: swarm <status|alt <sysid> <alt>|guided|clear>")
            return
            
        cmd = args[0]
        
        if cmd == "status":
            self.print_status()
        elif cmd == "alt":
            if len(args) != 3:
                print("Usage: swarm alt <sysid> <altitude>")
                return
            try:
                sysid = int(args[1])
                altitude = float(args[2])
                self.vehicle_altitudes[sysid] = altitude
                print(f"Set vehicle {sysid} altitude to {altitude}m")
            except ValueError:
                print("Invalid sysid or altitude. Usage: swarm alt <sysid> <altitude>")
        elif cmd == "guided":
            self.send_guided_commands()
        elif cmd == "clear":
            self.vehicle_altitudes.clear()
            print("Cleared all configured altitudes")
        else:
            print(f"Unknown command: {cmd}")
            print("Usage: swarm <status|alt <sysid> <alt>|guided|clear>")

    def print_status(self):
        '''print status of all vehicles'''
        print("\nConfigured Vehicles:")
        if not self.vehicle_altitudes:
            print("  (none)")
        else:
            for sysid, alt in sorted(self.vehicle_altitudes.items()):
                print(f"  Vehicle {sysid}: {alt}m altitude")
        
        print("\nDetected Vehicles:")
        if not self.detected_vehicles:
            print("  (none)")
        else:
            for sysid in sorted(self.detected_vehicles):
                status = "configured" if sysid in self.vehicle_altitudes else "not configured"
                print(f"  Vehicle {sysid}: {status}")
        print()

    def send_guided_commands(self):
        '''send guided command to all configured vehicles'''
        # Get click location
        latlon = self.mpstate.click_location
        if latlon is None:
            print("No map click position available")
            return
            
        lat, lon = latlon
        frame = mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT
        
        if not self.vehicle_altitudes:
            print("No vehicles configured. Use 'swarm alt <sysid> <altitude>' first.")
            return
            
        print(f"Sending {len(self.vehicle_altitudes)} vehicles to {lat}, {lon}")
        
        for sysid, altitude in sorted(self.vehicle_altitudes.items()):
            self.send_reposition_command(sysid, lat, lon, altitude)
            print(f"  Vehicle {sysid} → {altitude}m")

    def send_reposition_command(self, sysid, lat, lon, altitude):
        '''send MAV_CMD_DO_REPOSITION to a specific vehicle'''
        # Find the correct mavlink connection for this vehicle
        mav_link = self.get_mav_for_sysid(sysid)
        if mav_link is None:
            print(f"  Warning: Vehicle {sysid} not found on any link")
            return
            
        frame = mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT
        
        # Send reposition command
        mav_link.command_int_send(
            sysid,
            1,  # component ID
            frame,
            mavutil.mavlink.MAV_CMD_DO_REPOSITION,
            0,  # current
            0,  # autocontinue
            -1,  # p1 - ground speed, -1 is use-default
            mavutil.mavlink.MAV_DO_REPOSITION_FLAGS_CHANGE_MODE,  # p2 - flags
            0,  # p3 - loiter radius for Planes
            0,  # p4 - yaw
            int(lat * 1e7),
            int(lon * 1e7),
            altitude
        )

    def get_mav_for_sysid(self, sysid):
        '''find the mavlink interface for a given sysid'''
        if not hasattr(self.mpstate, 'vehicle_link_map'):
            return None
            
        for link_num, vehicle_list in self.mpstate.vehicle_link_map.items():
            if (sysid, 1) in vehicle_list or (sysid, mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1) in vehicle_list:
                if link_num < len(self.mpstate.mav_master):
                    return self.mpstate.mav_master[link_num].mav
        return None

    def mavlink_packet(self, m):
        '''handle incoming mavlink packets'''
        mtype = m.get_type()
        sysid = m.get_srcSystem()
        
        if mtype == 'HEARTBEAT' and m.type in self.valid_vehicles:
            self.detected_vehicles.add(sysid)
            self.vehicle_last_hb[sysid] = time.time()


def init(mpstate):
    return SwarmModule(mpstate)
