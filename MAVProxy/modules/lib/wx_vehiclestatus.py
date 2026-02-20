#!/usr/bin/env python3

"""
  wxWidgets vehicle status display window for MAVProxy
"""

import time

from MAVProxy.modules.lib.wx_loader import wx
from MAVProxy.modules.lib import win_layout
import wx.grid


class VehicleStatusFrame(wx.Frame):
    '''The main GUI frame for the vehicle status display'''
    
    def __init__(self, pipe_recv, pipe_send, title='Vehicle Status Display'):
        super(VehicleStatusFrame, self).__init__(None, title=title, size=(500, 300))
        
        self.pipe_recv = pipe_recv
        self.pipe_send = pipe_send
        self.vehicles = {}
        
        # Create panel
        panel = wx.Panel(self)
        
        # Create grid with 8 columns (added THR)
        self.grid = wx.grid.Grid(panel)
        self.grid.CreateGrid(0, 8)
        
        # Hide row labels (the numbers on the left side)
        self.grid.SetRowLabelSize(0)
        
        # Set smaller font for Linux displays
        font = wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.grid.SetDefaultCellFont(font)
        self.grid.SetLabelFont(font)
        
        # Set compact column labels
        self.grid.SetColLabelValue(0, "SYS")
        self.grid.SetColLabelValue(1, "MODE")
        self.grid.SetColLabelValue(2, "ALT")
        self.grid.SetColLabelValue(3, "ARSPD")
        self.grid.SetColLabelValue(4, "THR")
        self.grid.SetColLabelValue(5, "BAT1")
        self.grid.SetColLabelValue(6, "FUEL")
        self.grid.SetColLabelValue(7, "LINK")
        
        # Auto-size columns to fit content
        self.grid.AutoSizeColumns()
        
        # Set column widths for Linux displays (wider columns, smaller font)
        self.grid.SetColSize(0, 50)   # SYS
        self.grid.SetColSize(1, 80)   # MODE
        self.grid.SetColSize(2, 55)   # ALT
        self.grid.SetColSize(3, 60)   # ARSPD
        self.grid.SetColSize(4, 45)   # THR
        self.grid.SetColSize(5, 90)   # BAT1
        self.grid.SetColSize(6, 70)   # FUEL
        self.grid.SetColSize(7, 55)   # LINK
        
        # Make grid read-only
        self.grid.EnableEditing(False)
        
        # Create sizer with minimal margins
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.grid, 1, wx.EXPAND | wx.ALL, 2)
        panel.SetSizer(sizer)
        
        # Timer to check for updates from parent process
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer, self.timer)
        self.timer.Start(500)  # Check every 500ms
        
        # Handle close event
        self.Bind(wx.EVT_CLOSE, self.on_close)
        
        # Layout support - send window position/size periodically
        self.last_layout_send = time.time()
        self.Bind(wx.EVT_IDLE, self.on_idle)
        
    def on_timer(self, event):
        '''Check for updates from parent process'''
        while self.pipe_recv.poll():
            try:
                obj = self.pipe_recv.recv()
                if isinstance(obj, win_layout.WinLayout):
                    # Apply layout from parent (for restore)
                    win_layout.set_wx_window_layout(self, obj)
                else:
                    self.vehicles = obj
                    self.refresh_grid()
            except EOFError:
                break
                
    def refresh_grid(self):
        '''Refresh the grid with current vehicle data'''
        # Clear existing rows
        current_rows = self.grid.GetNumberRows()
        if current_rows > 0:
            self.grid.DeleteRows(0, current_rows)
        
        # Add new rows
        if not self.vehicles:
            return
            
        self.grid.AppendRows(len(self.vehicles))
        
        row = 0
        for sysid in sorted(self.vehicles.keys()):
            v = self.vehicles[sysid]
            
            # SYS ID
            self.grid.SetCellValue(row, 0, str(v.get('sysid', sysid)))
            self.grid.SetCellAlignment(row, 0, wx.ALIGN_CENTRE, wx.ALIGN_CENTRE)
            
            # MODE
            self.grid.SetCellValue(row, 1, str(v.get('mode', 'UNKNOWN')))
            self.grid.SetCellAlignment(row, 1, wx.ALIGN_CENTRE, wx.ALIGN_CENTRE)
            
            # ALT
            self.grid.SetCellValue(row, 2, "%.1f" % v.get('alt', 0.0))
            self.grid.SetCellAlignment(row, 2, wx.ALIGN_CENTRE, wx.ALIGN_CENTRE)
            
            # AIRSPEED
            self.grid.SetCellValue(row, 3, "%.1f" % v.get('airspeed', 0.0))
            self.grid.SetCellAlignment(row, 3, wx.ALIGN_CENTRE, wx.ALIGN_CENTRE)
            
            # THROTTLE
            self.grid.SetCellValue(row, 4, "%d" % int(v.get('throttle', 0)))
            self.grid.SetCellAlignment(row, 4, wx.ALIGN_CENTRE, wx.ALIGN_CENTRE)
            
            # BAT1
            bat1_voltage = v.get('bat1_voltage', 0.0)
            bat1_remaining = v.get('bat1_remaining', -1)
            if bat1_voltage > 0:
                if bat1_remaining >= 0:
                    bat1_str = "%.1fV (%d%%)" % (bat1_voltage, bat1_remaining)
                else:
                    bat1_str = "%.1fV" % bat1_voltage
                self.grid.SetCellValue(row, 5, bat1_str)
            else:
                self.grid.SetCellValue(row, 5, "--")
            self.grid.SetCellAlignment(row, 5, wx.ALIGN_CENTRE, wx.ALIGN_CENTRE)
            
            # Set battery color based on percentage
            if bat1_remaining >= 0:
                if bat1_remaining > 20:
                    self.grid.SetCellBackgroundColour(row, 5, wx.Colour(200, 255, 200))  # Green
                    self.grid.SetCellTextColour(row, 5, wx.Colour(0, 100, 0))  # Dark green text
                elif bat1_remaining > 10:
                    self.grid.SetCellBackgroundColour(row, 5, wx.Colour(255, 255, 200))  # Yellow
                    self.grid.SetCellTextColour(row, 5, wx.Colour(0, 100, 0))  # Dark green text
                else:
                    self.grid.SetCellBackgroundColour(row, 5, wx.Colour(255, 200, 200))  # Red
                    self.grid.SetCellTextColour(row, 5, wx.Colour(0, 100, 0))  # Dark green text
            
            # BAT2
            bat2_voltage = v.get('bat2_voltage', 0.0)
            if bat2_voltage > 0:
                self.grid.SetCellValue(row, 6, "%.1f" % bat2_voltage)
                self.grid.SetCellBackgroundColour(row, 6, wx.Colour(200, 255, 200))  # Green
                self.grid.SetCellTextColour(row, 6, wx.Colour(0, 100, 0))  # Dark green text
            else:
                self.grid.SetCellValue(row, 6, "--")
                self.grid.SetCellBackgroundColour(row, 6, wx.Colour(240, 240, 240))  # Gray
            self.grid.SetCellAlignment(row, 6, wx.ALIGN_CENTRE, wx.ALIGN_CENTRE)
            
            # LINK
            link_status = v.get('link_status', 'OK')
            self.grid.SetCellValue(row, 7, link_status)
            self.grid.SetCellAlignment(row, 7, wx.ALIGN_CENTRE, wx.ALIGN_CENTRE)
            # Set LINK color based on status
            if link_status == 'OK':
                self.grid.SetCellBackgroundColour(row, 7, wx.Colour(144, 238, 144))  # Light green
                self.grid.SetCellTextColour(row, 7, wx.Colour(0, 100, 0))  # Dark green text
            else:
                self.grid.SetCellBackgroundColour(row, 7, wx.Colour(255, 180, 180))  # Light red
                self.grid.SetCellTextColour(row, 7, wx.Colour(139, 0, 0))  # Dark red text
            
            # Set row color based on status
            if v.get('status') == 'stale':
                for col in range(8):
                    self.grid.SetCellBackgroundColour(row, col, wx.Colour(220, 220, 220))
                    self.grid.SetCellTextColour(row, col, wx.Colour(150, 150, 150))
            
            row += 1
            
        self.grid.Refresh()
        
    def on_idle(self, event):
        '''Send window layout to parent periodically'''
        now = time.time()
        if now - self.last_layout_send > 1:
            self.last_layout_send = now
            layout = win_layout.get_wx_window_layout(self)
            self.pipe_send.send(layout)

    def on_close(self, event):
        '''Handle window close event'''
        self.timer.Stop()
        self.Destroy()
