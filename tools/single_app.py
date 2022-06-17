import random
import threading
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
        self.event = _create_event(title)
        self.mutex = _create_mutex(title)
        # run only if no other one already is
        self.running = win32api.GetLastError() != winerror.ERROR_ALREADY_EXISTS
        if not self.running:
            # signal the running one
            win32event.SetEvent(self.event)

        self.callback = None
        self.thread = threading.Thread(target=self._check_another_started)
        self.thread.start()

    def __enter__(self):
        return self

    @property
    def already_running(self):
        return not self.running

    def set_callback_another_launched(self, callback):
        self.callback = callback

    def _check_another_started(self):
        while self.running:
            win32event.WaitForSingleObject(self.event, win32event.INFINITE)
            if self.callback:
                self.callback()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.running = False
        win32event.SetEvent(self.event)
        self.thread.join()

        for handle in (self.event, self.mutex):
            if handle:
                win32api.CloseHandle(handle)
