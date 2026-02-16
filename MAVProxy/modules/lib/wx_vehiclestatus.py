#!/usr/bin/env python3

"""
  wxWidgets vehicle status display window for MAVProxy
"""

import time

from MAVProxy.modules.lib.wx_loader import wx
import wx.grid


class VehicleStatusFrame(wx.Frame):
    '''The main GUI frame for the vehicle status display'''
    
    def __init__(self, pipe, title='Vehicle Status Display'):
        super(VehicleStatusFrame, self).__init__(None, title=title, size=(500, 300))
        
        self.pipe = pipe
        self.vehicles = {}
        
        # Create panel
        panel = wx.Panel(self)
        
        # Create grid with 8 columns (added THR)
        self.grid = wx.grid.Grid(panel)
        self.grid.CreateGrid(0, 8)
        
        # Hide row labels (the numbers on the left side)
        self.grid.SetRowLabelSize(0)
        
        # Set slightly larger font
        font = wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.grid.SetDefaultCellFont(font)
        self.grid.SetLabelFont(font)
        
        # Set compact column labels
        self.grid.SetColLabelValue(0, "SYS")
        self.grid.SetColLabelValue(1, "MODE")
        self.grid.SetColLabelValue(2, "ALT")
        self.grid.SetColLabelValue(3, "ARSPD")
        self.grid.SetColLabelValue(4, "THR")
        self.grid.SetColLabelValue(5, "BAT1")
        self.grid.SetColLabelValue(6, "BAT2")
        self.grid.SetColLabelValue(7, "HDG")
        
        # Auto-size columns to fit content
        self.grid.AutoSizeColumns()
        
        # Set smaller column widths to reduce empty space
        self.grid.SetColSize(0, 40)   # SYS
        self.grid.SetColSize(1, 70)   # MODE
        self.grid.SetColSize(2, 45)   # ALT
        self.grid.SetColSize(3, 50)   # ARSPD
        self.grid.SetColSize(4, 35)   # THR
        self.grid.SetColSize(5, 80)   # BAT1
        self.grid.SetColSize(6, 60)   # BAT2
        self.grid.SetColSize(7, 40)   # HDG
        
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
        
    def on_timer(self, event):
        '''Check for updates from parent process'''
        while self.pipe.poll():
            try:
                self.vehicles = self.pipe.recv()
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
                elif bat1_remaining > 10:
                    self.grid.SetCellBackgroundColour(row, 5, wx.Colour(255, 255, 200))  # Yellow
                else:
                    self.grid.SetCellBackgroundColour(row, 5, wx.Colour(255, 200, 200))  # Red
            
            # BAT2
            bat2_voltage = v.get('bat2_voltage', 0.0)
            if bat2_voltage > 0:
                self.grid.SetCellValue(row, 6, "%.1fV" % bat2_voltage)
                self.grid.SetCellBackgroundColour(row, 6, wx.Colour(200, 255, 200))  # Green
            else:
                self.grid.SetCellValue(row, 6, "--")
                self.grid.SetCellBackgroundColour(row, 6, wx.Colour(240, 240, 240))  # Gray
            self.grid.SetCellAlignment(row, 6, wx.ALIGN_CENTRE, wx.ALIGN_CENTRE)
            
            # HDG
            self.grid.SetCellValue(row, 7, "%d" % int(v.get('hdg', 0)))
            self.grid.SetCellAlignment(row, 7, wx.ALIGN_CENTRE, wx.ALIGN_CENTRE)
            
            # Set row color based on status
            if v.get('status') == 'stale':
                for col in range(8):
                    self.grid.SetCellBackgroundColour(row, col, wx.Colour(220, 220, 220))
                    self.grid.SetCellTextColour(row, col, wx.Colour(150, 150, 150))
            
            row += 1
            
        self.grid.Refresh()
        
    def on_close(self, event):
        '''Handle window close event'''
        self.timer.Stop()
        self.Destroy()
