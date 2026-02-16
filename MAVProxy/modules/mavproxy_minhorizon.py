"""
  MAVProxy minhorizon

  Minimal horizon indicator - shows horizon, altitude history, and battery
"""

from MAVProxy.modules.lib import wxminhorizon
from MAVProxy.modules.lib import mp_module
from MAVProxy.modules.lib.wxhorizon_util import Attitude, VFR_HUD, Global_Position_INT, BatteryInfo, FPS

import time

class MinHorizonModule(mp_module.MPModule):
    def __init__(self, mpstate):
        # Define module load/unload reference and window title
        super(MinHorizonModule, self).__init__(mpstate, "minhorizon", "Minimal Horizon Indicator", public=True)
        self.mpstate.minhorizonIndicator = wxminhorizon.MinHorizonIndicator(title='Minimal Horizon')
        self.msgList = []
        self.lastSend = 0.0
        self.fps = 10.0
        self.sendDelay = (1.0/self.fps)*0.9
        self.add_command('minhorizon-fps', self.fpsInformation, "Get or change frame rate for minhorizon.")
         
    def unload(self):
        '''unload module'''
        self.mpstate.minhorizonIndicator.close()
            
    def fpsInformation(self, args):
        '''fps command'''
        invalidStr = 'Invalid number of arguments. Usage: minhorizon-fps set <fps> or minhorizon-fps get.'
        if len(args) > 0:
            if args[0] == "get":
                if self.fps == 0.0:
                    print('MinHorizon Framerate: Unrestricted')
                else:
                    print("MinHorizon Framerate: " + str(self.fps))
            elif args[0] == "set":
                if len(args) == 2:
                    self.fps = float(args[1])
                    if self.fps != 0:
                        self.sendDelay = 1.0 / self.fps
                    else:
                        self.sendDelay = 0.0
                    self.msgList.append(FPS(self.fps))
                    if self.fps == 0.0:
                        print('MinHorizon Framerate: Unrestricted')
                    else:
                        print("MinHorizon Framerate: " + str(self.fps))
                else:
                    print(invalidStr)
            else:
                print(invalidStr)
        else:
            print(invalidStr)
            
    def mavlink_packet(self, msg):
        '''handle an incoming mavlink packet'''
        msgType = msg.get_type()
        
        if msgType == 'ATTITUDE':
            # Send attitude information down pipe (needed for horizon display)
            self.msgList.append(Attitude(msg))
        elif msgType == 'VFR_HUD':
            # Send HUD information down pipe (needed for heading)
            self.msgList.append(VFR_HUD(msg))
        elif msgType == 'GLOBAL_POSITION_INT':
            # Send altitude information down pipe
            self.msgList.append(Global_Position_INT(msg, time.time()))
        elif msgType == 'SYS_STATUS':
            # Send battery information down pipe
            self.msgList.append(BatteryInfo(msg))

    def idle_task(self):
        if self.mpstate.minhorizonIndicator.close_event.wait(0.001):
            self.needs_unloading = True
    
        if (time.time() - self.lastSend) > self.sendDelay:
            self.mpstate.minhorizonIndicator.parent_pipe_send.send(self.msgList)
            self.msgList = []
            self.lastSend = time.time()
    
def init(mpstate):
    '''initialise module'''
    return MinHorizonModule(mpstate)
