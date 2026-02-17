# MAVProxy Multi-Vehicle Enhancements

This document details the changes made to MAVProxy to improve multi-vehicle drone operations. These enhancements simplify the UI, improve usability when managing multiple drones, and add new functionality for swarm control.

## Overview

The following modules have been customized for multi-vehicle operations:
- **minconsole** - Minimal console display
- **multistatus** - Multi-vehicle status monitoring
- **minhorizon** - Minimal horizon instrument display
- **misseditor** - Simplified mission editor
- **swarm** - Multi-vehicle swarm control
- **map** - Map with improved defaults

---

## minconsole Module

A lightweight console display optimized for multi-vehicle operations.

### Changes Made

| Commit | Description |
|--------|-------------|
| `f16d138d` | Added minimal console module (minconsole) |
| `5654819b` | Fixed minconsole: properly remove all sensor fields and fix display labels |
| `8d91b755` | Fixed minconsole DIST and BRG labels to show field names with values |
| `f36d75a5` | Removed console field creation from fence and param modules |
| `d52e9c64` | Updated minconsole field names and layout |
| `e00ab7ce` | Added bold text support and update field names in minconsole |
| `b7f2455e` | Reverted bold text changes - fixes AttributeError in console module |
| `300ccccd` | Added colons to field names for consistent formatting |
| `5524e6f4` | Removed MAVProxy-calculated AGL, keep only vehicle-reported value |
| `60609b81` | Renamed SysID field to SYSID for consistency |
| `9828eefd` | Added font_size parameter to reduce console font size |
| `4275a0aa` | Simplified misseditor UI: remove WP Radius, Loiter Radius, Default Alt, CW checkbox, Home Location; move buttons to top row |
| `f699a2ac` | Reverted font_size changes - fixes AttributeError |
| `c484b9c0` | Simplified GPS display, move GPS to row 2, VCC/PWR to row 3, remove DIST, simplify HDG |
| `979334df` | Replaced PWR with AMP showing battery current from BATTERY_STATUS |
| `33ce9945` | AMP black, remove LINK; multistatus: replace HDG with LINK showing OK/DOWN |
| `7b201fdf` | Fix AMP to always show black |
| `d8625e4e` | Disable altitude announcements by default (altreadout=0) |
| `9160cf5c` | Reorder rows - LINK at bottom, no empty rows |
| `c8df7143` | Move LINK status to bottom row (row 5) |
| `0258b5bf` | Swap row 1 and 2 - LINK now on row 2, ALT/AGL/ARSPD/GNDSPD on row 1 |
| `86f5c24c` | Add PWR to initialization at correct position in row 3 |

### Display Layout

The final minconsole display is organized as follows:

- **Row 0**: Mode, SYSID, ARM, FLT TIME
- **Row 1**: ALT, AGL, ARSPD, GNDSPD
- **Row 2**: GPS, GPS2, WP, BRG, HDG
- **Row 3**: VCC, AMP, THR, ROLL, PITCH, YAW

Key simplifications:
- GPS shows only satellite count with color health indicator
- Displays vehicle-reported AGL (not MAVProxy-calculated)
- AMP shows battery current from BATTERY_STATUS
- LINK status removed from console (available in multistatus)
- Altitude announcements disabled by default (altreadout=0)

---

## multistatus Module

A dedicated multi-vehicle status monitoring window.

### Changes Made

| Commit | Description |
|--------|-------------|
| `ba4f8cc4` | Added vehicle status display module for multi-vehicle monitoring |
| `a1018f45` | Fixed vehicle_status module pipe handling |
| `2122e70c` | Fixed vehicle_status pipe handling to match working pattern |
| `d946cae6` | Fixed vehicle_status pipe handling - properly isolate child/parent pipe ends |
| `cb0b8e7a` | Rewrote vehicle_status module to match horizon pattern exactly |
| `287eaa53` | Fixed wx_vehiclestatus to handle missing data gracefully |
| `dc8e56f0` | Fixed mode display in vehicle_status module |
| `1134ae35` | Renamed vehicle_status module to multistatus and added to default modules |
| `d242d911` | Auto-open multistatus window on module load, remove from default modules |
| `4e4f47b2` | Added throttle data extraction from VFR_HUD messages |
| `0de4ade2` | Increased font size to 11, reduced column widths, reduced window size |
| `33ce9945` | Replaced HDG column with LINK showing OK/DOWN with colors |
| `dad1c8a9` | Improved LINK column colors - darker backgrounds with readable text |
| `93f730c5` | Renamed BAT2 column to FUEL |

### Features

- Auto-opens when module loads
- Shows status for all connected vehicles
- Columns: SYSID, MODE, ARM, GPS, ALT, FUEL, THR, LINK
- LINK column shows OK/DOWN with color coding (green for OK, red for DOWN)
- BAT2 column renamed to FUEL for clarity
- Font size increased to 11 for readability

---

## minhorizon Module (NEW)

A simplified horizon instrument display for multi-vehicle operations.

### Changes Made

| Commit | Description |
|--------|-------------|
| `93f730c5` | Added minhorizon module (in progress) |
| `b8454a13` | Fixed minhorizon UI module |

### Features

Created as a simplified version of the standard horizon module. Shows:
- Horizon (sky/ground representation)
- Pitch markers
- Heading/north pointers
- Altitude history plot
- Battery bar

Removed to simplify display:
- MODE, waypoints, distance/time to WP
- Roll/pitch/yaw text
- Voltage, amps, airspeed
- ALT, CR indicators

---

## misseditor Module

Mission editor UI simplified for multi-vehicle operations.

### Changes Made

| Commit | Description |
|--------|-------------|
| `4275a0aa` | Simplified misseditor UI: removed WP Radius, Loiter Radius, Default Alt, CW checkbox, Home Location sections; moved 4 buttons to top row |

### Simplifications

- **Removed sections:**
  - WP Radius
  - Loiter Radius
  - Default Alt
  - CW checkbox
  - Home Location

- **Layout changes:**
  - Moved 4 buttons to top row
  - Matched font size to multistatus (11)

---

## swarm Module

Multi-vehicle swarm control with simplified command interface.

### Changes Made

| Commit | Description |
|--------|-------------|
| `06c1c8b8` | Rewrote swarm module with simplified multi-vehicle control |
| `36ec0e5b` | Added command shortcuts for faster vehicle switching and guided mode |
| `99e9bd84` | Added new swarm2 module for multi-vehicle guided control |
| `a9a7432f` | Fixed swarm guided command to send to all vehicles, not just primary |
| `22e2c987` | Replaced swarm module with new implementation |

### Commands

The new swarm module provides the following commands:

| Command | Description |
|---------|-------------|
| `swarm alt <sysid> <alt>` | Set altitude for a specific vehicle |
| `swarm guided` | Send guided mode command to all vehicles |
| `swarm status` | Show swarm status |
| `swarm clear` | Clear swarm commands |

### Key Fix

- Original module only sent guided commands to primary vehicle
- Fixed to broadcast to all vehicles in the swarm

---

## map Module

Map display with improved defaults for multi-vehicle operations.

### Changes Made

| Commit | Description |
|--------|-------------|
| `e4119997` | Map module: default grid and follow to disabled |

### Changes

- Grid display disabled by default
- Follow mode disabled by default

---

## General Fixes

| Commit | Description |
|--------|-------------|
| `6f03c4ee` | Merged upstream master branch |
| `6bb5e3aa` | Adjusted horizon HUD layout: reduced text size and increased vertical spacing |

---

## Summary of Key Changes

1. **New Modules:**
   - `minconsole` - Minimal console display
   - `minhorizon` - Minimal horizon instrument display
   - `multistatus` - Multi-vehicle status monitoring

2. **Major Simplifications:**
   - Streamlined console display (fewer fields, cleaner layout)
   - Simplified mission editor UI
   - Removed unnecessary visual elements

3. **Multi-Vehicle Support:**
   - All displays show SYSID to identify vehicles
   - Swarm module for coordinated multi-vehicle control
   - Command shortcuts for faster vehicle switching

4. **Bug Fixes:**
   - Fixed bold text AttributeError (reverted)
   - Fixed font size issues (reverted)
   - Fixed pipe handling in vehicle_status
   - Fixed swarm guided command broadcast

5. **Usability Improvements:**
   - Auto-opening multistatus window
   - Improved color coding for LINK status
   - Disabled altitude announcements (altreadout=0)
   - Increased font sizes for readability

---

## Notes

- Some changes (bold text, font size adjustments) were initially attempted but caused AttributeError and were reverted
- The misseditor module does not have `multi_vehicle=True`, so it only receives HEARTBEAT from the primary vehicle
- All changes are maintained in the user's fork: https://github.com/vanfleet-dev/MAVProxy
