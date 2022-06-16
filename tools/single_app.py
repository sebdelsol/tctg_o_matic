import random
from uuid import UUID

import win32api
import win32event
import winerror


def _create_event(name):
    """auto reset event"""
    if event := win32event.CreateEvent(None, False, False, name):
        return event
    return win32event.OpenEvent(win32event.EVENT_ALL_ACCESS, 0, name)


def _create_mutex(name):
    """seed an uuid from the name"""
    rd = random.Random()
    rd.seed(name)
    mutexname = f"{{{UUID(int=rd.getrandbits(128))}}}"
    return win32event.CreateMutex(None, False, mutexname)


class SingleApp:
    """
    Limit app to a single instance
    Signal the running app another one has tried to start
    """

    def __init__(self, title):
        self.title = title
        self.event = None
        self.mutex = None
        self.mutex_error = None

    def __enter__(self):
        self.event = _create_event(self.title)
        self.mutex = _create_mutex(self.title)
        self.mutex_error = win32api.GetLastError()
        return self

    def is_running(self):
        if self.mutex_error == winerror.ERROR_ALREADY_EXISTS:
            print(f"{self.title} already running")
            # signal it has tried to start
            win32event.SetEvent(self.event)
            return True
        return False

    def has_tried_to_start(self):
        return win32event.WaitForSingleObject(self.event, 0) == win32event.WAIT_OBJECT_0

    def __exit__(self, exc_type, exc_val, exc_tb):
        for handle in (self.event, self.mutex):
            if handle:
                win32api.CloseHandle(handle)
