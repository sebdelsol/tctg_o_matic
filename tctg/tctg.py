import traceback
import webbrowser
from datetime import datetime

from tools import day_hour, err_file_line, loc_seconds_left
from tools.chrome import EnhancedChrome
from tools.schedule import Duration, Schedule
from tools.style import Style

from .events import Events
from .infos import InfosHandler

h0_grey = Style().bigger().grey40
h0 = Style().bigger().bold
grey = Style().grey40
h1 = Style().bold


class TCTG:
    x_reward = '//td[@class="rowfollow"]/text()[.="{reward:,}"]/following::td[1]/input'
    x_reward_done = '//*[contains(text(), "Toutes nos félicitations!")]'
    x_infos_block = '//table[@id="info_block"]'
    x_infos_txts = '(//span[@class="medium"])[1]'
    x_infos_msg = '(//td[@class="text"])[2]'
    x_rules = '//td[@class="embedded"]/ul'

    def __init__(self, config, event_callback):
        self.config = config
        self.event_callback = event_callback
        self.url = f"https://{self.config.domain}"
        self.running = True
        self.error = False
        self.infos = InfosHandler(config)
        self.show_infos()

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
        self.running = False
        self.schedule.stop()

    def force_update(self):
        self.schedule.force_update()

    def event(self, event, value):
        if self.running:
            self.event_callback(event, value)

    def log(self, *txts, main=False):
        prompt = Style("\n").smaller(5) if main else " •"
        self.event(Events.log, (prompt, " ", *txts))

    def log_error(self):
        err, file, line = err_file_line()
        file_line = " dans ", h0(file).red, " ligne ", h0(line).red
        self.log(h0(err).underline.red, *file_line)

    @staticmethod
    def get_date_txts(date):
        day, hour = day_hour(date)
        return " le ", h0_grey(day), " à ", h0_grey(hour)

    def log_update(self, scheduled):
        msg = "programmée" if scheduled else "forcée"
        self.log(
            h0(f"MàJ {msg}").warn(not scheduled).underline,
            *self.get_date_txts(datetime.now()),
            main=True,
        )

    def log_next(self, date):
        self.log(h1("Prochaine MàJ").blue, *self.get_date_txts(date))

    def log_left(self, seconds):
        error_msg = " (ERREUR)" if self.error else ""
        left = f"dans {loc_seconds_left(seconds)}{error_msg}"
        self.event(Events.log_left, h1(left).italic.warn(self.error))

    def show_infos(self):
        self.event(Events.show_infos, self.infos.get())

    def open_in_browser(self):
        webbrowser.open(self.url)

    def _update(self):
        self.event(Events.enable_update, False)
        self.event(Events.updating, h1("en cours").italic.white)
        self.error = False

        try:
            driver = EnhancedChrome(
                page_load_timeout=self.config.timeouts.page_load,
                wait_elt_timeout=self.config.timeouts.wait_elt,
            )
            driver.load_cookies(self.url)
            goto_page = lambda page: driver.get(f"{self.url}/{page}")

            with self.infos.updater(datetime.now()) as infos_updater:

                def update_infos():
                    goto_page("attendance.php")
                    driver.wait_for_clickable(TCTG.x_infos_block)
                    infos_txts = driver.xpath(TCTG.x_infos_txts).text
                    infos_msg = driver.xpath(TCTG.x_infos_msg).text
                    return infos_updater(infos_txts, infos_msg)

                # bonus ?
                if update_infos():
                    self.log(h0("Bonus du jour obtenu !!").green)
                    if self.config.get_bonus_rules:
                        with open("bonus_rules.txt", "w", encoding="utf8") as f:
                            f.write(driver.xpath(TCTG.x_rules).text)
                    update_infos()
                else:
                    self.log(Style("Bonus déjà obtenu aujourd'hui").green)

                # reward ?
                if self.infos.bonus >= self.config.reward:
                    self.log(h0("Cadeau obtenu !!").underline.green)
                    goto_page("mybonus.php")
                    x_reward = TCTG.x_reward.format(reward=self.config.reward)
                    driver.wait_for_clickable(x_reward).click()
                    driver.wait_for_clickable(TCTG.x_reward_done)
                    update_infos()

            self.show_infos()

        # pylint: disable=broad-except
        except Exception:
            self.error = True
            self.log_error()
            driver.save_error(traceback.format_exc(), datetime.now())

        finally:
            driver.quit()
            self.event(Events.enable_update, True)

        # notify error and sechedule a retry if needed
        self.event(Events.set_error, self.error)
        return self.retry if self.error else None
