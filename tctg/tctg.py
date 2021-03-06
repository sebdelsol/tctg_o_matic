import webbrowser
from datetime import datetime

from tools import day_hour, seconds_left_loc
from tools.chrome import Chrome
from tools.schedule import Duration, Schedule
from tools.style import Style

from .events import Events
from .infos import InfosHandler

h0_grey = Style().bigger().grey40
h0 = Style().bigger().bold
grey = Style().grey40
h1 = Style().bold


def _date_txts(date):
    day, hour = day_hour(date)
    return " le ", grey(day), " à ", h0_grey(hour)


class TCTG:
    def __init__(self, config, event_callback):
        self.config = config
        self.event = event_callback
        self.url = f"https://{self.config.domain}"
        self.error = False
        self.infos = InfosHandler(config)
        self.show_infos()

        self.chrome_kw = dict(
            page_load_timeout=self.config.timeouts.page_load,
            wait_elt_timeout=self.config.timeouts.wait_elt,
            log=self.log,
        )

        logs = dict(update=self.log_update, next=self.log_next, left=self.log_left)
        schedule = self.schedule = Schedule(self._update, **logs)

        self.log(h1("MàJ:").underline.blue, main=True)
        for at, jitter_minutes in config.everyday:
            every = schedule.every(1).days.at(at).jitter_add(jitter_minutes).minutes
            self.log(h1("Programmée: ").blue, grey(every))

        retry = config.retry
        self.retry = Duration(retry.hours).hours.jitter(retry.jitter_percent).percent
        self.log(h1("Si erreur: ").red, grey(self.retry))

        schedule.start(right_now=config.update_at_start)

    def stop(self):
        self.schedule.stop()

    def force_update(self):
        self.schedule.force_update()

    def log(self, *txts, main=False):
        prompt = Style("\n").smaller(5) if main else " •"
        self.event(Events.log, (prompt, " ", *txts))

    def log_update(self, scheduled):
        msg = "programmée" if scheduled else "forcée"
        update = h0(f"MàJ {msg}").warn(not scheduled).underline
        self.log(update, *_date_txts(datetime.now()), main=True)

    def log_next(self, date):
        self.log(h1("Prochaine MàJ").blue, *_date_txts(date))

    def log_left(self, seconds):
        error_msg = " (ERREUR)" if self.error else ""
        left = h1(f"dans {seconds_left_loc(seconds)}{error_msg}")
        self.event(Events.log_left, left.italic.warn(self.error))

    def log_error(self, err):
        self.log(
            h0(err.name).underline.red,
            " dans ",
            h0(err.file).red,
            " ligne ",
            h0(err.line).red,
        )

    def show_infos(self):
        self.event(Events.show_infos, self.infos.get())

    def open_in_browser(self):
        webbrowser.open(self.url)

    def _update(self):
        self.event(Events.enable_update, False)
        self.event(Events.updating, h1("en cours").italic.white)

        infos = self.infos
        rwrd = self.config.reward.pts
        x_reward = f"//td[@class='rowfollow']/text()[.='{rwrd:,}']/following::input[1]"
        x_reward_done = "//*[contains(text(), 'Toutes nos félicitations!')]"
        x_infos = (
            "(//span[@class='medium'])[1]",  # infos_txt
            "//a[@href='messages.php']/..",  # mailbox_txt
            "(//td[@class='text'])[2]",  # attendance_txt
        )
        x_infos_block = "//table[@id='info_block']"
        x_rules = "//td[@class='embedded']/ul"

        with Chrome(**self.chrome_kw) as driver:
            driver.load_cookies(self.url)
            with infos.updater(datetime.now()) as infos_updater:

                def goto_page(page):
                    return driver.get(f"{self.url}/{page}")

                def update_infos():
                    goto_page("attendance.php")
                    driver.wait_for_clickable(x_infos_block)
                    return infos_updater(*(driver.xpath(x).text for x in x_infos))

                # bonus ?
                if update_infos():
                    self.log(h0("Bonus du jour obtenu !!").green)
                    bonus_rules = driver.xpath(x_rules).text
                    if infos.check_config_bonus(bonus_rules):
                        self.log(h0("MàJ des règles Bonus !!").underline.red)
                    update_infos()
                else:
                    self.log(Style("Bonus déjà obtenu aujourd'hui").green)

                # reward ?
                if infos.bonus >= rwrd:
                    self.log(h0("Cadeau obtenu !!").underline.green)
                    goto_page("mybonus.php")
                    driver.wait_for_clickable(x_reward).click()
                    driver.wait_for_clickable(x_reward_done)
                    update_infos()

            self.show_infos()

        self.event(Events.enable_update, True)

        self.error = bool(driver.error)
        self.event(Events.set_tray_icon, self.error)
        if self.error:
            self.log_error(driver.error)
            return self.retry  # schedule a retry
        return None
