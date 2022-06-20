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
        self._event = _create_event(title)
        self._mutex = _create_mutex(title)
        # run only if no other one already is
        self.can_run = win32api.GetLastError() != winerror.ERROR_ALREADY_EXISTS
        if not self.can_run:
            print(f"\n{title} already running!!")

        self._callback = None
        self._thread = threading.Thread(target=self._check_another_started)
        self._thread.start()

    def __enter__(self):
        return self

    def set_callback_another_launched(self, callback):
        self._callback = callback

    def _check_another_started(self):
        while self.can_run:
            win32event.WaitForSingleObject(self._event, win32event.INFINITE)
            if self._callback:
                self._callback()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.can_run = False
        # stop waiting waiting & signal the already running one
        win32event.SetEvent(self._event)
        self._thread.join()

        for handle in (self._event, self._mutex):
            if handle:
                win32api.CloseHandle(handle)
