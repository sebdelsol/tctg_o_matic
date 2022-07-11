from dataclasses import dataclass
from datetime import datetime

from tools.loader import YamlMapping, YamlSequence

SECONDS_A_HOUR = 3600
SECONDS_A_DAY = SECONDS_A_HOUR * 24


@dataclass
class Bonus(YamlMapping):
    date: datetime
    bonus: float
    dbonus: float

    def days_to(self, end):
        return (end.date.date() - self.date.date()).days

    def seconds_to(self, end):
        return (end.date - self.date).total_seconds()

    def bonus_to(self, end):
        return end.bonus - self.bonus


class Bonuses(list, YamlSequence):
    def add(self, **bonus):
        # does this bonus occured after the last recorded one ?
        if len(self) == 0 or bonus["date"] > self[-1].date:
            self.append(Bonus(**bonus))

    def _set(self, new_list):
        self.clear()
        self.extend(new_list)

    def _pairs(self):  # [0, 1, 2] -> [[0, 1], [1, 2]]
        return list(zip(iter(self), iter(self[1:])))

    def speed(self, config):
        if len(self) >= 2:
            dt = 0
            bonus = 0
            for begin, end in self._pairs():
                dt += begin.seconds_to(end)
                bonus += begin.bonus_to(end) - end.dbonus
            # do we have enough to compute speed ?
            if dt >= config.bonuses.compute_speed_min_hours * SECONDS_A_HOUR:
                return bonus * SECONDS_A_DAY / dt
        return None

    def crop(self, config):
        if len(self) >= 2:
            config = config.bonuses
            # remove those older than some days from now
            dt = 0
            crop_older_than = config.crop_older_than_days * SECONDS_A_DAY
            for begin, end in reversed(self._pairs()):
                dt += begin.seconds_to(end)
                if dt >= crop_older_than:
                    crop_index = self.index(begin)
                    self._set(self[crop_index:])
                    break

            # compress by at least some hours slice
            dt = 0
            compressed = [self[0]]
            compress_less_than = config.compress_less_than_hours * SECONDS_A_HOUR
            for begin, end in self._pairs():
                dt += begin.seconds_to(end)
                if end.dbonus > 0 or dt >= compress_less_than:
                    compressed.append(end)
                    dt = 0
            if end not in compressed:
                compressed.append(end)
            self._set(compressed)

            # crop before an event that breaks the speed computation
            for begin, end in reversed(self._pairs()):
                cross_days = begin.days_to(end)
                if (
                    (cross_days == 1 and end.dbonus == 0)  # missing bonus
                    or begin.bonus_to(end) < 0  # consummed bonus
                    or cross_days > 1  # cross more than one day
                ):
                    crop_index = self.index(end)
                    self._set(self[crop_index:])
                    break
