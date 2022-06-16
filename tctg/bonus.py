from dataclasses import dataclass
from datetime import datetime

from tools.loader import YamlMapping, YamlSequence


@dataclass
class Bonus(YamlMapping):
    date: datetime
    bonus: float
    dbonus: float


class Bonuses(list, YamlSequence):
    a_hour = 3600  # seconds
    a_day = a_hour * 24  # seconds
    _seconds = lambda begin, end: (end.date - begin.date).total_seconds()

    def add(self, **bonus):
        # does this bonus occured after the last recorded one ?
        if len(self) == 0 or bonus["date"] > self[-1].date:
            self.append(Bonus(**bonus))

    def _set(self, new_list):
        self.clear()
        self.extend(new_list)

    def _two_by_two(self, reverse=False):
        return zip(self[-2::-1], self[:0:-1]) if reverse else zip(self[:-1], self[1:])

    def speed(self, config):
        if len(self) >= 2:
            dt = 0
            bonus = 0
            dbonus = 0
            for begin, end in self._two_by_two():
                dt += Bonuses._seconds(begin, end)
                bonus += end.bonus - begin.bonus
                dbonus += end.dbonus

            # do we have enough to compute speed ?
            if dt >= config.bonuses.compute_speed_min_hours * self.a_hour:
                return (bonus - dbonus) * self.a_day / dt
        return None

    def crop(self, config):
        if len(self) >= 2:
            # remove those older than some days from now
            dt = 0
            crop_older_than = config.bonuses.crop_older_than_days * self.a_day
            for begin, end in self._two_by_two(reverse=True):
                dt += Bonuses._seconds(begin, end)
                if dt >= crop_older_than:
                    crop_index = self.index(begin)
                    self._set(self[crop_index:])
                    break

            # compress by at least some hours slice
            dt = 0
            compressed = [self[0]]
            compress_less_than = config.bonuses.compress_less_than_hours * self.a_hour
            for begin, end in self._two_by_two():
                dt += Bonuses._seconds(begin, end)
                if end.dbonus > 0 or dt >= compress_less_than:
                    compressed.append(end)
                    dt = 0
            if end not in compressed:
                compressed.append(end)
            self._set(compressed)

            # crop before an event that breaks the speed computation
            for begin, end in self._two_by_two(reverse=True):
                cross_days = (end.date.date() - begin.date.date()).days
                if (
                    (cross_days == 1 and end.dbonus == 0)  # missing bonus
                    or end.bonus - begin.bonus < 0  # consummed bonus
                    or cross_days > 1  # cross more than one day
                ):
                    crop_index = self.index(end)
                    self._set(self[crop_index:])
                    break
