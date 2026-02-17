#!/usr/bin/env python3

"""
  MAVProxy minimal horizon indicator.
"""
from MAVProxy.modules.lib import multiproc
from MAVProxy.modules.lib import win_layout
import threading
import time

class MinHorizonIndicator():
    '''
    A minimal horizon indicator for MAVProxy.
    '''
    def __init__(self, title='MAVProxy: Minimal Horizon'):
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

        # Start watch thread to receive layouts from child process
        self.watch_thread = threading.Thread(target=self.watch_thread_func)
        self.watch_thread.daemon = True
        self.watch_thread.start()

    def child_task(self):
        '''child process - this holds all the GUI elements'''
        self.parent_pipe_send.close()
        self.parent_pipe_recv.close()

        from MAVProxy.modules.lib import wx_processguard
        from MAVProxy.modules.lib.wx_loader import wx
        from MAVProxy.modules.lib.wxminhorizon_ui import MinHorizonFrame
        # Create wx application
        app = wx.App(False)
        app.frame = MinHorizonFrame(state=self, pipe_recv=self.child_pipe_recv, pipe_send=self.child_pipe_send, title=self.title)
        app.frame.SetDoubleBuffered(True)
        app.frame.Show()
        app.MainLoop()
        self.close_event.set()   # indicate that the GUI has closed

    def watch_thread_func(self):
        '''Watch for layout events from child process'''
        try:
            while True:
                if self.parent_pipe_recv.poll(0.1):
                    msg = self.parent_pipe_recv.recv()
                    if isinstance(msg, win_layout.WinLayout):
                        win_layout.set_layout(msg, self.set_layout)
                time.sleep(0.1)
        except (EOFError, BrokenPipeError):
            pass

    def set_layout(self, layout):
        '''set window layout - callback for layout system'''
        try:
            self.parent_pipe_send.send(layout)
        except Exception:
            pass

    def close(self):
        '''Close the window.'''
        self.close_event.set()
        if self.is_alive():
            self.child.join(2)

    def is_alive(self):
        '''check if child is still going'''
        return self.child.is_alive()

if __name__ == "__main__":
    # test the console
    multiproc.freeze_support()
    horizon = MinHorizonIndicator()
    while horizon.is_alive():
        print('test')
        time.sleep(0.5)
