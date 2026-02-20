#!/usr/bin/env python3

"""
  MAVProxy vehicle status display module

  Displays status information for all connected vehicles in a grid format
"""

from MAVProxy.modules.lib import mp_module
from MAVProxy.modules.lib import mp_util
from MAVProxy.modules.lib import multiproc
from MAVProxy.modules.lib import win_layout
from pymavlink import mavutil
import threading
import time


class MultiStatusModule(mp_module.MPModule):
    def __init__(self, mpstate):
        super(MultiStatusModule, self).__init__(mpstate, "multistatus", "Multi-Vehicle Status Display", public=True, multi_vehicle=True)
        
        # Vehicle data storage: {sysid: {'mode': x, 'alt': y, ...}}
        self.vehicles = {}
        
        # Add commands
        self.add_command('multistatus', self.cmd_multistatus, "multi-vehicle status display", ['show', 'hide', 'enable', 'disable', 'clear'])
        
        # Settings
        self.enabled = True
        self.window_visible = False
        self.update_interval = 2.0  # seconds
        self.last_update = 0
        
        # GUI window - create automatically when module loads
        self.indicator = None
        self.watch_thread = None
        self.create_window()
        self.window_visible = True
        
        print("Multi-status module loaded. Window opened automatically.")
        
    def mavlink_packet(self, msg):
        '''Process incoming MAVLink packets from all vehicles'''
        if not self.enabled or not self.window_visible or not self.indicator:
            return
            
        msg_type = msg.get_type()
        sysid = msg.get_srcSystem()
        
        # Skip SYS_ID 0 - invalid system ID
        if sysid == 0:
            return
        
        # Initialize vehicle entry if new
        if sysid not in self.vehicles:
            self.vehicles[sysid] = {
                'sysid': sysid,
                'mode': 'UNKNOWN',
                'alt': 0.0,
                'airspeed': 0.0,
                'throttle': 0,
                'bat1_voltage': 0.0,
                'bat1_remaining': -1,
                'bat2_voltage': 0.0,
                'link_status': 'OK',
                'last_seen': time.time(),
                'status': 'active'
            }
        
        # Update last seen time and reset link status
        self.vehicles[sysid]['last_seen'] = time.time()
        self.vehicles[sysid]['link_status'] = 'OK'
        
        # Process different message types
        if msg_type == 'HEARTBEAT':
            # Get mode from heartbeat
            mode_map = mavutil.mode_mapping_bynumber(msg.type)
            if mode_map and msg.custom_mode in mode_map:
                self.vehicles[sysid]['mode'] = mode_map[msg.custom_mode]
            else:
                self.vehicles[sysid]['mode'] = "UNKNOWN"
            
        elif msg_type == 'GLOBAL_POSITION_INT':
            # Convert mm to meters for altitude
            self.vehicles[sysid]['alt'] = msg.relative_alt / 1000.0
            # Convert centidegrees to degrees for heading
            if msg.hdg != 65535:  # 65535 means unknown
                self.vehicles[sysid]['hdg'] = msg.hdg / 100.0
                
        elif msg_type == 'VFR_HUD':
            self.vehicles[sysid]['airspeed'] = msg.airspeed
            self.vehicles[sysid]['throttle'] = msg.throttle
            
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
            
    def cmd_multistatus(self, args):
        '''Handle multistatus commands'''
        if len(args) < 1:
            print("Usage: multistatus <show|hide|enable|disable|clear>")
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
            print("Multi-status window shown")
            
        elif cmd == 'hide':
            if self.window_visible and self.indicator:
                self.close_window()
            self.window_visible = False
            print("Multi-status window hidden")
            
        elif cmd == 'enable':
            self.enabled = True
            if not self.window_visible:
                self.create_window()
                self.window_visible = True
            print("Multi-status updates enabled")
            
        elif cmd == 'disable':
            self.enabled = False
            print("Multi-status updates disabled")
            
        elif cmd == 'clear':
            self.vehicles = {}
            print("Multi-status data cleared")
            
        else:
            print("Unknown command: %s" % cmd)
            print("Usage: multistatus <show|hide|enable|disable|clear>")
            
    def create_window(self):
        '''Create the GUI window using multiprocessing'''
        if self.indicator is not None and self.indicator.is_alive():
            return

        self.indicator = MultiStatusIndicator(title='Multi-Vehicle Status')

        # Start watch thread to receive layouts from child process
        self.watch_thread = threading.Thread(target=self.watch_thread_func)
        self.watch_thread.daemon = True
        self.watch_thread.start()

    def watch_thread_func(self):
        '''Watch for layout events from child process'''
        try:
            while True:
                if self.indicator and self.indicator.parent_pipe_recv.poll(0.1):
                    msg = self.indicator.parent_pipe_recv.recv()
                    if isinstance(msg, win_layout.WinLayout):
                        win_layout.set_layout(msg, self.set_layout)
                time.sleep(0.1)
        except (EOFError, BrokenPipeError):
            pass

    def set_layout(self, layout):
        '''set window layout - callback for layout system'''
        if self.indicator:
            try:
                self.indicator.parent_pipe_send.send(layout)
            except Exception:
                pass
        
    def close_window(self):
        '''Close the GUI window'''
        if self.indicator:
            self.indicator.close()
            self.indicator = None
        if self.watch_thread:
            self.watch_thread = None
        
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
                vehicle['link_status'] = 'DOWN'
            else:
                vehicle['status'] = 'active'
                vehicle['link_status'] = 'OK'
                
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


class MultiStatusIndicator():
    '''A multi-vehicle status indicator for MAVProxy.'''
    def __init__(self, title='MAVProxy: Multi-Status'):
        self.title = title
        # Create two pipes: one for parent->child (data), one for child->parent (layouts)
        self.child_pipe_recv, self.parent_pipe_send = multiproc.Pipe()
        self.parent_pipe_recv, self.child_pipe_send = multiproc.Pipe()
        self.close_event = multiproc.Event()
        self.close_event.clear()
        self.child = multiproc.Process(target=self.child_task)
        self.child.start()
        self.child_pipe_recv.close()
        self.child_pipe_send.close()

    def child_task(self):
        '''Child process - this holds all the GUI elements'''
        self.parent_pipe_send.close()
        self.parent_pipe_recv.close()
        
        from MAVProxy.modules.lib import wx_processguard
        from MAVProxy.modules.lib.wx_loader import wx
        from MAVProxy.modules.lib.wx_vehiclestatus import VehicleStatusFrame
        
        # Create wx application
        app = wx.App(False)
        app.frame = VehicleStatusFrame(pipe_recv=self.child_pipe_recv, pipe_send=self.child_pipe_send, title=self.title)
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
    return MultiStatusModule(mpstate)
