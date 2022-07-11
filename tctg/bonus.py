from dataclasses import dataclass
from datetime import datetime

from tools.loader import YamlMapping, YamlSequence


@dataclass
class Bonus(YamlMapping):
    date: datetime
    bonus: float
    dbonus: float

    def seconds_to(self, end):
        return (end.date - self.date).total_seconds()

    def bonus_to(self, end):
        return end.bonus - self.bonus


class Bonuses(list, YamlSequence):
    a_hour = 3600  # seconds
    a_day = a_hour * 24  # seconds

    def add(self, **bonus):
        # does this bonus occured after the last recorded one ?
        if len(self) == 0 or bonus["date"] > self[-1].date:
            self.append(Bonus(**bonus))

    def _set(self, new_list):
        self.clear()
        self.extend(new_list)

    def _pairs(self):  # [[0, 1], [1, 2], [2, 3], ...]
        return list(zip(iter(self), iter(self[1:])))

    def speed(self, config):
        if len(self) >= 2:
            dt = 0
            bonus = 0
            for begin, end in self._pairs():
                dt += begin.seconds_to(end)
                bonus += begin.bonus_to(end) - end.dbonus

            # do we have enough to compute speed ?
            if dt >= config.bonuses.compute_speed_min_hours * Bonuses.a_hour:
                return bonus * Bonuses.a_day / dt
        return None

    def crop(self, config):
        if len(self) >= 2:
            config = config.bonuses
            # remove those older than some days from now
            dt = 0
            crop_older_than = config.crop_older_than_days * Bonuses.a_day
            for begin, end in reversed(self._pairs()):
                dt += begin.seconds_to(end)
                if dt >= crop_older_than:
                    crop_index = self.index(begin)
                    self._set(self[crop_index:])
                    break

            # compress by at least some hours slice
            dt = 0
            compressed = [self[0]]
            compress_less_than = config.compress_less_than_hours * Bonuses.a_hour
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
                cross_days = (end.date.date() - begin.date.date()).days
                if (
                    (cross_days == 1 and end.dbonus == 0)  # missing bonus
                    or begin.bonus_to(end) < 0  # consummed bonus
                    or cross_days > 1  # cross more than one day
                ):
                    crop_index = self.index(end)
                    self._set(self[crop_index:])
                    break
