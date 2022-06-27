import random
import threading
from datetime import datetime, timedelta
from types import SimpleNamespace

from . import timedelta_loc


class Duration:
    time_units = "days", "hours", "minutes", "seconds"

    def __init__(self, duration=0):
        self._duration = duration
        self._jitter = timedelta()
        self._jitter_boundaries = 0, 0
        self._at_hour = None
        self._date = None

    def from_now(self, now=None):
        assert isinstance(self._duration, timedelta), "need a duration unit"
        assert isinstance(self._jitter, timedelta), "need a jitter unit"
        assert self._duration > timedelta(), "duration has to be > 0"
        assert self._jitter >= timedelta(), "duration has to be >= 0"

        now = now or datetime.now()
        if self._at_hour:
            self._date = datetime.combine(now, self._at_hour.time())
        else:
            self._date = now + self._duration

        # date possible with min jitter needs to be >= now
        min_jitter = self._jitter * min(self._jitter_boundaries)
        while self._date + min_jitter < now:
            self._date += self._duration

        # add rnd jitter
        self._date += self._jitter * random.uniform(*self._jitter_boundaries)
        return self

    @property
    def date(self):
        return self._date

    def left(self, now=None):
        now = now or datetime.now()
        return (self._date - now).total_seconds()

    def at(self, at_hour):
        self._at_hour = datetime.strptime(at_hour, "%H:%M")
        return self

    def to(self, to_hour):
        assert self._at_hour, "at(hour) needs to be set"
        self._jitter_boundaries = 0, 1
        self._jitter = datetime.strptime(to_hour, "%H:%M") - self._at_hour
        assert self._jitter >= timedelta(), "to(hour) needs to be >= at(hour)"
        return self

    def jitter(self, jitter, add=False):
        self._jitter_boundaries = 0 if add else -1, 1
        self._jitter = jitter
        return self

    def jitter_add(self, jitter):
        return self.jitter(jitter, add=True)

    @property
    def percent(self):
        assert not isinstance(self._jitter, timedelta), "need a jitter value"
        self._jitter_boundaries = -(percent := self._jitter / 100), percent
        self._jitter = self._duration
        return self

    def __getattr__(self, unit):
        assert unit in Duration.time_units, f"Duration object has no time {unit=}"
        if isinstance(self._duration, timedelta):
            # duration already set, then it's about jitter
            assert not isinstance(self._jitter, timedelta), "need a jitter value"
            self._jitter = timedelta(**{unit: self._jitter})
        else:
            self._duration = timedelta(**{unit: self._duration})
        return self

    @staticmethod
    def _unit_if_only_one(txt):
        if len(txt.split(",")) == 1:
            value, unit = txt.split()
            if int(value) == 1:
                return unit
        return txt

    def __repr__(self):
        txt = f"Chaque {self._unit_if_only_one(timedelta_loc(self._duration))}"
        if self._at_hour:
            txt += f" à {self._at_hour:%Hh%M}"
        if self._jitter >= timedelta():
            min_, max_ = self._jitter_boundaries
            txt += f" ~ {'+' if min_ == 0 else '±'}{timedelta_loc(self._jitter * max_)}"
        return txt


class Schedule:
    """run a job in a background thread"""

    log_funcs = "update", "left", "next"

    def __init__(self, job, **logs):
        """
        job : might return a Duration object to schedule its next call
        """
        self._run = threading.Thread(target=self._loop)
        self._force_update = threading.Event()
        self._running = False
        self._next_in = None
        self._everys = []
        self._job = job
        logs = {name: logs.get(name, lambda _: None) for name in Schedule.log_funcs}
        self.log = SimpleNamespace(**logs)

    def start(self, right_now):
        self._resume_from_now(right_now=right_now)
        self._running = True
        self._run.start()

    def stop(self):
        self._running = False
        self.force_update()
        self._run.join()

    def force_update(self):
        self._force_update.set()

    def every(self, duration):
        every = Duration(duration)
        self._everys.append(every)
        return every

    def _tick(self):
        left = self._next_in.left()
        self.log.left(max(0, left))
        return left <= 0

    def _resume_from_now(self, next_in=None, right_now=False):
        if self._everys or next_in:
            now = datetime.now()
            nexts = self._everys + ([next_in] if next_in else [])
            nexts = [n.from_now(now) for n in nexts]
            nexts.sort(key=lambda n: n.left(now))
            self._next_in = nexts[0]

            if right_now:
                self.force_update()
            else:
                self.log.next(self._next_in.date)
                self._force_update.clear()
        else:
            raise ValueError("Nothing has been scheduled")

    def _loop(self):
        while self._running:
            # actual sleep happens in the wait()
            if self._tick() or self._force_update.wait(1):
                if self._running:  # faster exit
                    scheduled = not self._force_update.is_set()
                    self.log.update(scheduled)
                    next_in = self._job()
                    self._resume_from_now(next_in)
