#!/usr/bin/env python3

"""
  MAVProxy vehicle status display module

  Displays status information for all connected vehicles in a grid format
"""

from MAVProxy.modules.lib import mp_module
from MAVProxy.modules.lib import mp_util
from MAVProxy.modules.lib import multiproc
from pymavlink import mavutil
import time


class VehicleStatusModule(mp_module.MPModule):
    def __init__(self, mpstate):
        super(VehicleStatusModule, self).__init__(mpstate, "vehicle_status", "Vehicle Status Display", public=True, multi_vehicle=True)
        
        # Vehicle data storage: {sysid: {'mode': x, 'alt': y, ...}}
        self.vehicles = {}
        
        # Add commands
        self.add_command('vstat', self.cmd_vstat, "vehicle status display", ['show', 'hide', 'enable', 'disable', 'clear'])
        
        # Settings
        self.enabled = True
        self.window_visible = False
        self.update_interval = 2.0  # seconds
        self.last_update = 0
        
        # GUI window - will be created on demand
        self.indicator = None
        
        print("Vehicle status module loaded. Use 'vstat show' to open window.")
        
    def mavlink_packet(self, msg):
        '''Process incoming MAVLink packets from all vehicles'''
        if not self.enabled or not self.window_visible or not self.indicator:
            return
            
        msg_type = msg.get_type()
        sysid = msg.get_srcSystem()
        
        # Initialize vehicle entry if new
        if sysid not in self.vehicles:
            self.vehicles[sysid] = {
                'sysid': sysid,
                'mode': 'UNKNOWN',
                'alt': 0.0,
                'airspeed': 0.0,
                'bat1_voltage': 0.0,
                'bat1_remaining': -1,
                'bat2_voltage': 0.0,
                'hdg': 0,
                'last_seen': time.time(),
                'status': 'active'
            }
        
        # Update last seen time
        self.vehicles[sysid]['last_seen'] = time.time()
        
        # Process different message types
        if msg_type == 'HEARTBEAT':
            # Get mode from heartbeat
            mode_map = mavutil.mode_mapping_bynumber.get(msg.type, {})
            mode = mode_map.get(msg.custom_mode, "UNKNOWN")
            self.vehicles[sysid]['mode'] = mode
            
        elif msg_type == 'GLOBAL_POSITION_INT':
            # Convert mm to meters for altitude
            self.vehicles[sysid]['alt'] = msg.relative_alt / 1000.0
            # Convert centidegrees to degrees for heading
            if msg.hdg != 65535:  # 65535 means unknown
                self.vehicles[sysid]['hdg'] = msg.hdg / 100.0
                
        elif msg_type == 'VFR_HUD':
            self.vehicles[sysid]['airspeed'] = msg.airspeed
            
        elif msg_type == 'SYS_STATUS':
            # Convert mV to V for battery 1
            self.vehicles[sysid]['bat1_voltage'] = msg.voltage_battery / 1000.0
            self.vehicles[sysid]['bat1_remaining'] = msg.battery_remaining
            
        elif msg_type == 'BATTERY2':
            # Convert mV to V for battery 2
            self.vehicles[sysid]['bat2_voltage'] = msg.voltage / 1000.0
            
        elif msg_type == 'BATTERY_STATUS':
            # Handle BATTERY_STATUS message if available
            if msg.id == 0:  # Battery 1
                self.vehicles[sysid]['bat1_voltage'] = msg.voltages[0] / 1000.0 if msg.voltages[0] != 65535 else 0.0
                self.vehicles[sysid]['bat1_remaining'] = msg.battery_remaining
            elif msg.id == 1:  # Battery 2
                self.vehicles[sysid]['bat2_voltage'] = msg.voltages[0] / 1000.0 if msg.voltages[0] != 65535 else 0.0
            
    def cmd_vstat(self, args):
        '''Handle vstat commands'''
        if len(args) < 1:
            print("Usage: vstat <show|hide|enable|disable|clear>")
            print("  show    - Show the status window")
            print("  hide    - Hide the status window")
            print("  enable  - Enable status updates")
            print("  disable - Disable status updates")
            print("  clear   - Clear all vehicle data")
            return
            
        cmd = args[0].lower()
        
        if cmd == 'show':
            if not self.window_visible:
                self.create_window()
            self.window_visible = True
            print("Vehicle status window shown")
            
        elif cmd == 'hide':
            if self.window_visible and self.indicator:
                self.close_window()
            self.window_visible = False
            print("Vehicle status window hidden")
            
        elif cmd == 'enable':
            self.enabled = True
            if not self.window_visible:
                self.create_window()
                self.window_visible = True
            print("Vehicle status updates enabled")
            
        elif cmd == 'disable':
            self.enabled = False
            print("Vehicle status updates disabled")
            
        elif cmd == 'clear':
            self.vehicles = {}
            print("Vehicle status data cleared")
            
        else:
            print("Unknown command: %s" % cmd)
            print("Usage: vstat <show|hide|enable|disable|clear>")
            
    def create_window(self):
        '''Create the GUI window using multiprocessing'''
        if self.indicator is not None and self.indicator.is_alive():
            return
            
        self.indicator = VehicleStatusIndicator(title='Vehicle Status Display')
        
    def close_window(self):
        '''Close the GUI window'''
        if self.indicator:
            self.indicator.close()
            self.indicator = None
        
    def update_display(self):
        '''Update the GUI with current vehicle data'''
        if not self.window_visible or not self.indicator or not self.indicator.is_alive():
            return
            
        # Check for stale vehicles (no heartbeat for 10+ seconds)
        now = time.time()
        stale_threshold = 10.0
        
        for sysid in list(self.vehicles.keys()):
            vehicle = self.vehicles[sysid]
            if now - vehicle['last_seen'] > stale_threshold:
                vehicle['status'] = 'stale'
            else:
                vehicle['status'] = 'active'
                
        # Send data to GUI process
        try:
            self.indicator.parent_pipe_send.send(self.vehicles)
        except Exception as e:
            pass
            
    def unload(self):
        '''Unload the module'''
        self.close_window()
        
    def idle_task(self):
        '''Periodic updates - called regularly by MAVProxy'''
        if not self.enabled or not self.window_visible or not self.indicator:
            return
            
        if not self.indicator.is_alive():
            self.needs_unloading = True
            return
            
        now = time.time()
        if now - self.last_update >= self.update_interval:
            self.update_display()
            self.last_update = now


class VehicleStatusIndicator():
    '''A vehicle status indicator for MAVProxy.'''
    def __init__(self, title='MAVProxy: Vehicle Status'):
        self.title = title
        # Create Pipe to send vehicle data from module to UI
        self.child_pipe_recv, self.parent_pipe_send = multiproc.Pipe()
        self.close_event = multiproc.Event()
        self.close_event.clear()
        self.child = multiproc.Process(target=self.child_task)
        self.child.start()
        self.child_pipe_recv.close()

    def child_task(self):
        '''Child process - this holds all the GUI elements'''
        self.parent_pipe_send.close()
        
        from MAVProxy.modules.lib import wx_processguard
        from MAVProxy.modules.lib.wx_loader import wx
        from MAVProxy.modules.lib.wx_vehiclestatus import VehicleStatusFrame
        
        # Create wx application
        app = wx.App(False)
        app.frame = VehicleStatusFrame(pipe=self.child_pipe_recv, title=self.title)
        app.frame.Show()
        app.MainLoop()
        self.close_event.set()

    def close(self):
        '''Close the window.'''
        self.close_event.set()
        if self.is_alive():
            self.child.join(2)

    def is_alive(self):
        '''Check if child is still going'''
        return self.child.is_alive()


def init(mpstate):
    '''Required initialization function'''
    return VehicleStatusModule(mpstate)
