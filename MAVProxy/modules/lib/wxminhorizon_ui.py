import time
from MAVProxy.modules.lib.wxhorizon_util import Attitude, VFR_HUD, Global_Position_INT, BatteryInfo, FPS
from MAVProxy.modules.lib.wx_loader import wx
from MAVProxy.modules.lib import win_layout
import math, time

import matplotlib
matplotlib.use('wxAgg')
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.pyplot import Polygon
import matplotlib.patheffects as PathEffects
from matplotlib import patches
import matplotlib as mpl


class MinHorizonFrame(wx.Frame):
    """ The main frame of the minimal horizon indicator."""

    def __init__(self, state, pipe_recv, pipe_send, title):
        self.state = state
        self.pipe_recv = pipe_recv
        self.pipe_send = pipe_send
        # Create Frame and Panel(s)
        wx.Frame.__init__(self, None, title=title)
        state.frame = self

        # Initialisation
        self.initData()
        self.initUI()
        self.startTime = time.time()
        self.nextTime = 0.0
        self.fps = 10.0

    def initData(self):
        # Initialise Attitude
        self.pitch = 0.0  # Degrees
        self.roll = 0.0   # Degrees
        
        # Initialise Altitude Info
        self.relAlt = 0.0 # m relative to home position
        self.relAltTime = 0.0 # s The time that the relative altitude was recorded
        self.altHist = [] # Altitude History
        self.timeHist = [] # Time History
        self.altMax = 0.0 # Maximum altitude since startup
        
        # Initialise Heading
        self.heading = 0.0 # 0-360
        
        # Initialise Battery Info
        self.batRemain = 0.0

    def initUI(self):
        # Create Event Timer and Bindings
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer, self.timer)
        self.timer.Start(100)
        self.Bind(wx.EVT_IDLE, self.on_idle)

        # Create Panel
        self.panel = wx.Panel(self)
        self.vertSize = 0.03
        self.resized = False
        
        # Create Matplotlib Panel
        self.createPlotPanel()

        # Fix Axes - vertical is of length 2, horizontal keeps the same lengthscale
        self.rescaleX()
        self.calcFontScaling()        
        
        # Create Horizon Polygons
        self.createHorizonPolygons()
        
        # Center Pointer Marker
        self.thick = 0.015
        self.createCenterPointMarker()
        
        # Pitch Markers
        self.dist10deg = 0.2 # Graph distance per 10 deg
        self.createPitchMarkers()
        
        # Create Heading Pointer
        self.createHeadingPointer()
        
        # Create North Pointer
        self.createNorthPointer()
        
        # Create Battery Bar (only the colored box)
        self.batWidth = 0.1
        self.batHeight = 0.2
        self.rOffset = 0.35
        self.createBatteryBar()
        
        # Create Altitude History Plot
        self.createAltHistoryPlot()
        
        # Show Frame
        self.Show(True)
        self.pending = []
    
    def createPlotPanel(self):
        '''Creates the figure and axes for the plotting panel.'''
        self.figure = Figure()
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvas(self, -1, self.figure)
        self.canvas.SetSize(wx.Size(300,300))
        self.axes.axis('off')
        self.figure.subplots_adjust(left=0, right=1, top=1, bottom=0)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.canvas, 1, wx.EXPAND, wx.ALL)
        self.SetSizerAndFit(self.sizer)
        self.Fit()
        
    def rescaleX(self):
        '''Rescales the horizontal axes to make the lengthscales equal.'''
        self.ratio = self.figure.get_size_inches()[0] / float(self.figure.get_size_inches()[1])
        self.axes.set_xlim(-self.ratio, self.ratio)
        self.axes.set_ylim(-1, 1)
        
    def calcFontScaling(self):
        '''Calculates the current font size and left position for the current window.'''
        dpi = 100.0
        self.ypx = self.figure.get_size_inches()[1] * dpi
        self.xpx = self.figure.get_size_inches()[0] * dpi
        self.fontSize = self.vertSize * (self.ypx / 2.0)
        self.leftPos = self.axes.get_xlim()[0]
        self.rightPos = self.axes.get_xlim()[1]
    
    def checkResize(self):
        '''Checks if the window was resized.'''
        if not self.resized:
            oldypx = self.ypx
            oldxpx = self.xpx
            dpi = 100.0
            self.ypx = self.figure.get_size_inches()[1] * dpi
            self.xpx = self.figure.get_size_inches()[0] * dpi
            if (oldypx != self.ypx) or (oldxpx != self.xpx):
                self.resized = True
            else:
                self.resized = False
    
    def createHeadingPointer(self):
        '''Creates the pointer for the current heading.'''
        self.headingTri = patches.RegularPolygon((0.0, 0.80), 3, radius=0.05, color='k', zorder=4)
        self.axes.add_patch(self.headingTri)
        self.headingText = self.axes.text(0.0, 0.675, '0', color='k', size=self.fontSize, horizontalalignment='center', verticalalignment='center', zorder=4)
    
    def adjustHeadingPointer(self):
        '''Adjust the value of the heading pointer.'''
        self.headingText.set_text(str(self.heading))
        self.headingText.set_size(self.fontSize) 
    
    def createNorthPointer(self):
        '''Creates the north pointer relative to current heading.'''
        self.headingNorthTri = patches.RegularPolygon((0.0, 0.80), 3, radius=0.05, color='k', zorder=4)
        self.axes.add_patch(self.headingNorthTri)
        self.headingNorthText = self.axes.text(0.0, 0.675, 'N', color='k', size=self.fontSize, horizontalalignment='center', verticalalignment='center', zorder=4)    

    def adjustNorthPointer(self):
        '''Adjust the position and orientation of the north pointer.'''
        self.headingNorthText.set_size(self.fontSize) 
        headingRotate = mpl.transforms.Affine2D().rotate_deg_around(0.0, 0.0, self.heading) + self.axes.transData
        self.headingNorthText.set_transform(headingRotate)
        if (self.heading > 90) and (self.heading < 270):
            headRot = self.heading - 180
        else:
            headRot = self.heading
        self.headingNorthText.set_rotation(headRot)
        self.headingNorthTri.set_transform(headingRotate)
        if (self.heading <= 10.0) or (self.heading >= 350.0):
            self.headingNorthText.set_text('')
        else:
            self.headingNorthText.set_text('N')
            
    def createCenterPointMarker(self):
        '''Creates the center pointer in the middle of the screen.'''
        self.axes.add_patch(patches.Rectangle((-0.75, -self.thick), 0.5, 2.0 * self.thick, facecolor='orange', zorder=3))
        self.axes.add_patch(patches.Rectangle((0.25, -self.thick), 0.5, 2.0 * self.thick, facecolor='orange', zorder=3))
        self.axes.add_patch(patches.Circle((0, 0), radius=self.thick, facecolor='orange', edgecolor='none', zorder=3))
        
    def createHorizonPolygons(self):
        '''Creates the two polygons to show the sky and ground.'''
        vertsTop = [[-1, 0], [-1, 1], [1, 1], [1, 0], [-1, 0]]
        self.topPolygon = Polygon(vertsTop, facecolor='dodgerblue', edgecolor='none')
        self.axes.add_patch(self.topPolygon)
        vertsBot = [[-1, 0], [-1, -1], [1, -1], [1, 0], [-1, 0]]
        self.botPolygon = Polygon(vertsBot, facecolor='brown', edgecolor='none')
        self.axes.add_patch(self.botPolygon)
        
    def calcHorizonPoints(self):
        '''Updates the verticies of the patches for the ground and sky.'''
        ydiff = math.tan(math.radians(-self.roll)) * float(self.ratio)
        pitchdiff = self.dist10deg * (self.pitch / 10.0)
        if (self.roll > 90) or (self.roll < -90):
            pitchdiff = pitchdiff * -1
        vertsTop = [(-self.ratio, ydiff - pitchdiff), (-self.ratio, 1), (self.ratio, 1), (self.ratio, -ydiff - pitchdiff), (-self.ratio, ydiff - pitchdiff)]
        vertsBot = [(-self.ratio, ydiff - pitchdiff), (-self.ratio, -1), (self.ratio, -1), (self.ratio, -ydiff - pitchdiff), (-self.ratio, ydiff - pitchdiff)]
        if (self.roll > 90) or (self.roll < -90):
            vertsTop = [(-self.ratio, ydiff - pitchdiff), (-self.ratio, -1), (self.ratio, -1), (self.ratio, -ydiff - pitchdiff), (-self.ratio, ydiff - pitchdiff)]
            vertsBot = [(-self.ratio, ydiff - pitchdiff), (-self.ratio, 1), (self.ratio, 1), (self.ratio, -ydiff - pitchdiff), (-self.ratio, ydiff - pitchdiff)]
        self.topPolygon.set_xy(vertsTop)
        self.botPolygon.set_xy(vertsBot)  
    
    def createPitchMarkers(self):
        '''Creates the rectangle patches for the pitch indicators.'''
        self.pitchPatches = []
        for i in [-9, -8, -7, -6, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]:
            width = self.calcPitchMarkerWidth(i)
            currPatch = patches.Rectangle((-width / 2.0, self.dist10deg * i - (self.thick / 2.0)), width, self.thick, facecolor='w', edgecolor='none')
            self.axes.add_patch(currPatch)
            self.pitchPatches.append(currPatch)
        self.vertSize = 0.03
        self.pitchLabelsLeft = []
        self.pitchLabelsRight = []
        i = 0
        for j in [-90, -60, -30, 30, 60, 90]:
            self.pitchLabelsLeft.append(self.axes.text(-0.55, (j / 10.0) * self.dist10deg, str(j), color='w', size=self.fontSize, horizontalalignment='center', verticalalignment='center'))
            self.pitchLabelsLeft[i].set_path_effects([PathEffects.withStroke(linewidth=1, foreground='k')])
            self.pitchLabelsRight.append(self.axes.text(0.55, (j / 10.0) * self.dist10deg, str(j), color='w', size=self.fontSize, horizontalalignment='center', verticalalignment='center'))
            self.pitchLabelsRight[i].set_path_effects([PathEffects.withStroke(linewidth=1, foreground='k')])
            i += 1
        
    def calcPitchMarkerWidth(self, i):
        '''Calculates the width of a pitch marker.'''
        if (i % 3) == 0:
            if i == 0:
                width = 1.5
            else:
                width = 0.9
        else:
            width = 0.6
        return width
            
    def adjustPitchmarkers(self):
        '''Adjusts the location and orientation of pitch markers.'''
        pitchdiff = self.dist10deg * (self.pitch / 10.0)
        rollRotate = mpl.transforms.Affine2D().rotate_deg_around(0.0, -pitchdiff, self.roll) + self.axes.transData
        j = 0
        for i in [-9, -8, -7, -6, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]:
            width = self.calcPitchMarkerWidth(i)
            self.pitchPatches[j].set_xy((-width / 2.0, self.dist10deg * i - (self.thick / 2.0) - pitchdiff))
            self.pitchPatches[j].set_transform(rollRotate)
            j += 1
        i = 0
        for j in [-9, -6, -3, 3, 6, 9]:
            self.pitchLabelsLeft[i].set_y(j * self.dist10deg - pitchdiff)
            self.pitchLabelsRight[i].set_y(j * self.dist10deg - pitchdiff)
            self.pitchLabelsLeft[i].set_size(self.fontSize)
            self.pitchLabelsRight[i].set_size(self.fontSize)
            self.pitchLabelsLeft[i].set_rotation(self.roll)
            self.pitchLabelsRight[i].set_rotation(self.roll)
            self.pitchLabelsLeft[i].set_transform(rollRotate)
            self.pitchLabelsRight[i].set_transform(rollRotate)
            i += 1
                
    def createBatteryBar(self):
        '''Creates the bar to display current battery percentage.'''
        self.batOutRec = patches.Rectangle((self.rightPos - (1.3 + self.rOffset) * self.batWidth, 1.0 - (0.1 + 1.0 + (2 * 0.075)) * self.batHeight), self.batWidth * 1.3, self.batHeight * 1.15, facecolor='darkgrey', edgecolor='none')
        self.batInRec = patches.Rectangle((self.rightPos - (self.rOffset + 1 + 0.15) * self.batWidth, 1.0 - (0.1 + 1 + 0.075) * self.batHeight), self.batWidth, self.batHeight, facecolor='lawngreen', edgecolor='none')
        self.axes.add_patch(self.batOutRec)
        self.axes.add_patch(self.batInRec)
        
    def updateBatteryBar(self):
        '''Updates the position of the battery bar.'''
        self.batOutRec.set_xy((self.rightPos - (1.3 + self.rOffset) * self.batWidth, 1.0 - (0.1 + 1.0 + (2 * 0.075)) * self.batHeight))
        self.batInRec.set_xy((self.rightPos - (self.rOffset + 1 + 0.15) * self.batWidth, 1.0 - (0.1 + 1 + 0.075) * self.batHeight))
        if self.batRemain >= 0:
            self.batInRec.set_height(self.batRemain * self.batHeight / 100.0)
            if self.batRemain / 100.0 > 0.5:
                self.batInRec.set_facecolor('lawngreen')
            elif self.batRemain / 100.0 <= 0.5 and self.batRemain / 100.0 > 0.2:
                self.batInRec.set_facecolor('yellow')
            elif self.batRemain / 100.0 <= 0.2 and self.batRemain >= 0.0:
                self.batInRec.set_facecolor('r')
        elif self.batRemain == -1:
            self.batInRec.set_height(self.batHeight)
            self.batInRec.set_facecolor('k')
        
    def createAltHistoryPlot(self):
        '''Creates the altitude history plot.'''
        self.altHistRect = patches.Rectangle((self.leftPos + (self.vertSize / 10.0), -0.25), 0.5, 0.5, facecolor='grey', edgecolor='none', alpha=0.4, zorder=4)
        self.axes.add_patch(self.altHistRect)
        self.altPlot, = self.axes.plot([self.leftPos + (self.vertSize / 10.0), self.leftPos + (self.vertSize / 10.0) + 0.5], [0.0, 0.0], color='k', marker=None, zorder=4)
        self.altMarker, = self.axes.plot(self.leftPos + (self.vertSize / 10.0) + 0.5, 0.0, marker='o', color='k', zorder=4)
        self.altText2 = self.axes.text(self.leftPos + (4 * self.vertSize / 10.0) + 0.5, 0.0, '%.f m' % self.relAlt, color='k', size=self.fontSize, ha='left', va='center', zorder=4)
    
    def updateAltHistory(self):
        '''Updates the altitude history plot.'''
        self.altHist.append(self.relAlt)
        self.timeHist.append(self.relAltTime)
        
        currentTime = time.time()
        point = 0
        for i in range(0, len(self.timeHist)):
            if (self.timeHist[i] > (currentTime - 10.0)):
                break
        self.altHist = self.altHist[i:]
        self.timeHist = self.timeHist[i:]
        
        x = []
        y = []
        tmin = min(self.timeHist)
        tmax = max(self.timeHist)
        x1 = self.leftPos + (self.vertSize / 10.0)
        y1 = -0.25
        altMin = 0
        altMax = max(self.altHist)
        if altMax > self.altMax:
            self.altMax = altMax
        else:
            altMax = self.altMax
        if tmax != tmin:
            mx = 0.5 / (tmax - tmin)
        else:
            mx = 0.0
        if altMax != altMin:
            my = 0.5 / (altMax - altMin)
        else:
            my = 0.0
        for t in self.timeHist:
            x.append(mx * (t - tmin) + x1)
        for alt in self.altHist:
            val = my * (alt - altMin) + y1
            if val < -0.25:
                val = -0.25
            elif val > 0.25:
                val = 0.25
            y.append(val)
        self.altHistRect.set_x(self.leftPos + (self.vertSize / 10.0))
        self.altPlot.set_data(x, y)
        self.altMarker.set_data([self.leftPos + (self.vertSize / 10.0) + 0.5], [val])
        self.altText2.set_position((self.leftPos + (4 * self.vertSize / 10.0) + 0.5, val))
        self.altText2.set_size(self.fontSize)
        self.altText2.set_text('%.f m' % self.relAlt)
        
    def on_idle(self, event):
        self.checkResize()

        if self.resized:
            self.rescaleX()
            self.calcFontScaling()
            self.calcHorizonPoints()
            self.adjustPitchmarkers()
            self.adjustHeadingPointer()
            self.adjustNorthPointer()
            self.updateBatteryBar()
            self.updateAltHistory()
            self.canvas.draw()
            self.canvas.Refresh()
            self.resized = False

        # Send layout to parent periodically
        if not hasattr(self, 'last_layout_send'):
            self.last_layout_send = time.time()
        now = time.time()
        if now - self.last_layout_send > 1:
            self.last_layout_send = now
            layout = win_layout.get_wx_window_layout(self)
            self.pipe_send.send(layout)

        time.sleep(0.05)
 
    def on_timer(self, event):
        state = self.state
        self.loopStartTime = time.time()
        if state.close_event.wait(0.001):
            self.timer.Stop()
            self.Destroy()
            return
        
        self.checkResize()
        if self.resized:
            self.on_idle(0)
        
        while self.pipe_recv.poll():
            obj = self.pipe_recv.recv()
            # Handle layout restoration from parent
            if isinstance(obj, win_layout.WinLayout):
                win_layout.set_wx_window_layout(self, obj)
                continue
            # obj is a list of message objects
            for item in obj:
                self.calcFontScaling()
                if isinstance(item, Attitude):
                    self.pitch = item.pitch * 180 / math.pi
                    self.roll = item.roll * 180 / math.pi
                    self.calcHorizonPoints()
                    self.adjustPitchmarkers()

                elif isinstance(item, VFR_HUD):
                    self.heading = item.heading
                    self.adjustHeadingPointer()
                    self.adjustNorthPointer()

                elif isinstance(item, Global_Position_INT):
                    self.relAlt = item.relAlt
                    self.relAltTime = item.curTime
                    self.updateAltHistory()

                elif isinstance(item, BatteryInfo):
                    self.batRemain = item.batRemain
                    self.updateBatteryBar()
        
        if (time.time() > self.nextTime):                     
            self.canvas.draw()
            self.canvas.Refresh()                 
            self.Refresh()
            self.Update()
            
            if (self.fps > 0):
                fpsTime = 1 / self.fps
                self.nextTime = fpsTime + self.loopStartTime
            else:
                self.nextTime = time.time()
