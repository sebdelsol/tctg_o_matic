import re
from bisect import bisect
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from types import SimpleNamespace

from tools import day_hour, number, plural
from tools.loader import Loader, YamlMapping
from tools.style import Style

from .bonus import Bonuses

interline = Style("\n").smaller(4)
row = lambda *args: (*args, "\n")
h0 = Style().bold.bigger(7)
h1 = Style().bold.bigger(3)
h2 = Style().bold.bigger()
h3 = Style
h4 = Style().smaller()
h5 = Style().smaller(2)


@dataclass
class Infos(YamlMapping):
    date: datetime = datetime.now()
    connected: bool = False
    bonus: float = 0
    dbonus: float = 0
    ratio: float = 0
    ul: tuple = field(default_factory=lambda: (0, ""))
    dl: tuple = field(default_factory=lambda: (0, ""))
    seeding: int = 0
    click_days: int = 0
    consecutive_days: int = 0
    bonus_date: datetime = None
    bonuses: Bonuses = field(default_factory=Bonuses)
    speed: int = 0
    reward_in_days: int = 0


class InfosHandler:
    def __init__(self, config):
        self.config = config
        self.loader = Loader(config.infos_file)
        self.infos = self.loader.load() or Infos()

    def save(self):
        self.loader.save(self.infos)

    def _update(self, infos_txt, msg, update_date):
        infos = self.infos

        raw = re.sub(r"\[[\w\s]+\]|Torrents", "", infos_txt)
        raw = [e.strip() for e in re.split(r"(\w+\s?):", raw)[1:]]
        raw = dict(zip((k.lower() for k in raw[::2]), raw[1::2]))
        raw = SimpleNamespace(**raw)

        bonus, dbonus = re.findall(r"[,\.\d]+", raw.bonus)
        ul = raw.envoyé.split()
        dl = raw.téléchargé.split()

        if "jour" in msg:
            click_days, consecutive_days = re.findall(r"(\d+)", msg)[:2]
            infos.bonus_date = update_date
        else:
            click_days = infos.click_days or 0
            consecutive_days = infos.consecutive_days or 0

        infos.date = update_date
        infos.connected = raw.connectable == "Oui"
        infos.bonus = float(bonus.replace(",", ""))
        infos.dbonus = float(dbonus.replace(",", ""))
        infos.ratio = float("inf") if raw.ratio == "Inf." else float(raw.ratio)
        infos.ul = float(ul[0]), ul[1]
        infos.dl = float(dl[0]), dl[1]
        infos.seeding = int(raw.actifs.split()[0])
        infos.click_days = int(click_days)
        infos.consecutive_days = int(consecutive_days)

        return update_date == infos.bonus_date  # got_bonus

    def _update_end(self):
        config = self.config
        infos = self.infos

        # add bonus & update speed
        got_bonus = infos.date == infos.bonus_date
        infos.bonuses.add(
            date=infos.date,
            bonus=infos.bonus,
            dbonus=infos.dbonus if got_bonus else 0,
        )
        infos.bonuses.crop(config)
        infos.speed = round(infos.bonuses.speed(config) or infos.speed or 0)

        # update reward_in_days
        bonus_days, bonus_pts = zip(*config.bonus.consecutive_days)
        bonus_pts = (0,) + bonus_pts

        def bonus_consecutive(day):
            return bonus_pts[bisect(bonus_days, day)]

        consecutive_days = infos.consecutive_days
        dbonus = infos.dbonus - bonus_consecutive(consecutive_days)
        left = config.reward.pts - infos.bonus
        infos.reward_in_days = 0
        while left > 0:
            infos.reward_in_days += 1
            consecutive_days += 1
            dbonus = min(dbonus + config.bonus.added_per_day, config.bonus.max)
            left -= dbonus + bonus_consecutive(consecutive_days) + infos.speed

    @contextmanager
    def updater(self, update_date):
        try:
            yield partial(self._update, update_date=update_date)
        finally:
            self._update_end()
            self.save()

    @property
    def bonus(self):
        return self.infos.bonus

    def get(self):
        infos = self.infos
        config = self.config
        day, hour = day_hour(infos.date)
        rows = (
            *row(h0(config.title).blue),
            *row(h2(day).blue, h4(" à ").blue, h2(hour).blue),
            *row(
                h3(f"{'' if infos.connected else 'Pas '}Connecté").warn(
                    not infos.connected
                )
            ),
            interline,
            *row(h1("Bonus ").blue, *number(h1(infos.bonus).green)),
            *row(
                h3(infos.click_days).blue,
                h5(f" {plural('jour', infos.click_days)},  "),
                h2(infos.consecutive_days).blue,
                h5(" de suite"),
            ),
            *row(*number(h3(infos.dbonus).blue), h5(" pts/jour")),
            interline,
            *row(
                h1("Ratio ").blue,
                *number(
                    h1("∞" if infos.ratio == float("inf") else infos.ratio).warn(
                        infos.ratio <= 1
                    )
                ),
            ),
            *row(
                h2(config.UI.up_arrow).green,
                *number(h2(infos.ul[0]).green),
                h5(f" {infos.ul[1]}  "),
                h2(f"{config.UI.up_arrow}{infos.seeding}").warn(infos.seeding == 0),
                h5(f" {plural('seed', infos.seeding)}"),
            ),
            *row(
                h2(config.UI.down_arrow).red,
                *number(h2(infos.dl[0]).red),
                h5(f" {infos.dl[1]}"),
            ),
            interline,
            *row(
                h1("Reward ").blue,
                *number(h1(config.reward.pts).green),
            ),
            *row(
                *number(h2(config.reward.gb).green),
                h5(" GB dans "),
                h2(infos.reward_in_days).blue,
                h5(f" {plural('jour', infos.reward_in_days)}"),
            ),
            *row(
                *number(h3(round(infos.speed + infos.dbonus)).blue),
                h5(" pts/jour, "),
                *number(
                    h3(
                        config.reward.gb
                        * (infos.speed + infos.dbonus)
                        / config.reward.pts
                    ).blue,
                    2,
                ),
                h5(" GB/jour"),
            ),
        )
        return rows[:-1]  # remove the last "\n" from row()
