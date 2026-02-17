#!/usr/bin/env python3
'''
simplified mission editor module for multi-vehicle operations
'''

from MAVProxy.modules.lib import mp_module

class MinMissionEditorModule(mp_module.MPModule):
    '''
    A Simplified Mission Editor for multi-vehicle operations
    '''
    def __init__(self, mpstate):
        super(MinMissionEditorModule, self).__init__(mpstate, "minmisseditor", "mission editor", public = True)

        # to work around an issue on MacOS this module is a thin wrapper around a separate MissionEditorMain object
        from MAVProxy.modules.mavproxy_minmisseditor import mission_editor
        self.me_main = mission_editor.MissionEditorMain(mpstate, self.module('terrain').ElevationModel.database)

    def unload(self):
        '''unload module'''
        self.me_main.unload()

    def idle_task(self):
        self.me_main.idle_task()
        if self.me_main.needs_unloading:
            self.needs_unloading = True

    def mavlink_packet(self, m):
        self.me_main.mavlink_packet(m)

    def click_updated(self):
        self.me_main.update_map_click_position(self.mpstate.click_location)

def init(mpstate):
    '''initialise module'''
    return MinMissionEditorModule(mpstate)
