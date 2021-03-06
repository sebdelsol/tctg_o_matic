"""
88888888888 .d8888b. 88888888888 .d8888b.
    888    d88P  Y88b    888    d88P  Y88b
    888    888    888    888    888    888
    888    888           888    888
    888    888           888    888  88888
    888    888    888    888    888    888
    888    Y88b  d88P    888    Y88b  d88P
    888     "Y8888P"     888     "Y8888P88
"""

import PySimpleGUI as sg
from psgtray import SystemTray
from tools import img_to64, widgets

from .events import Events
from .tctg import TCTG


class TCTGWindow(widgets.Window):
    logo = img_to64("icons/logo.ico", height=22)
    ok_ico = img_to64("icons/logo.ico")
    error_ico = img_to64("icons/error.ico")

    def __init__(self, app, config):
        font = config.UI.font
        font_bold = f"{font} bold"

        self.tray = SystemTray(
            ["", []],
            window=self,
            single_click_events=True,
            icon=TCTGWindow.ok_ico,
        )
        Events.tray_click = self.tray.key

        self.logs = widgets.MLineColors(
            font=(font, 8),
            background_color=config.UI.log,
            sbar_background_color=sg.theme_background_color(),
            sbar_arrow_color=sg.theme_button_color_background(),
            border_width=0,
            auto_refresh=False,
            write_only=True,
            disabled=True,
            expand_x=True,
            expand_y=True,
        )
        self.b_update = widgets.ButtonMouseOver(
            "MàJ",
            font=(font_bold, 10),
            k=Events.update,
        )
        self.left = widgets.AnimatedTxt(
            "",
            font=(font, 10),
            colors=vars(config.UI.infos),
            size=(20, None),
        )
        self.infos = widgets.MLineAutoSize(
            "",
            font=(font, 9),
            justification="center",
            background_color=sg.theme_background_color(),
            text_color=sg.theme_element_text_color(),
            pad=(5, 2),
            colors=vars(config.UI.infos),
        )
        b_logo = widgets.ButtonCooldown(
            "",
            image_data=TCTGWindow.logo,
            cooldown=2000,
            button_color=sg.theme_background_color(),
            over_color=sg.theme_button_color_background(),
            border_width=0,
            k=Events.logo,
        )
        b_quit = widgets.ButtonMouseOver(
            "Quitter",
            font=(font, 10),
            over_color="red",
            k=Events.close,
        )
        b_minimize = widgets.ButtonMouseOver(
            "_____",
            over_color="lime green",
            font=(font_bold, 12),
            k=Events.minimize,
        )
        self.yes_no_kw = dict(
            title=f"Quitter {config.title} ?",
            yes=("oui", "red"),
            no=("non", "lime green"),
            font=(font_bold, 12),
        )

        event_to_action = {
            Events.tray_click: lambda _: self.UnHide() if self._Hidden else self.Hide(),
            Events.enable_update: lambda enabled: self.b_update(disabled=not enabled),
            Events.updating: lambda txt: self.left(txt, animated=True),
            Events.logo: lambda _: self.tctg.open_in_browser(),
            Events.update: lambda _: self.tctg.force_update(),
            Events.set_tray_icon: self.set_tray_icon,
            Events.close: lambda _: self.ask_close(),
            Events.unhide: lambda _: self.UnHide(),
            Events.minimize: lambda _: self.Hide(),
            Events.show_infos: self.show_infos,
            Events.log_left: self.left,
            Events.log: self.log,
        }

        menu = [b_logo, b_quit, self.b_update, self.left, sg.P(), b_minimize]
        super().__init__(
            config.title,
            [[self.infos, sg.Col([menu, [self.logs]], expand_y=True)]],
            event_to_action=event_to_action,
            element_padding=(2, 2),
            alpha_channel=0,
        )
        app.set_callback_another_started(lambda: self.write_event_value(Events.unhide))
        self.tctg = TCTG(config, self.write_event_value)

    def set_tray_icon(self, error):
        self.tray.change_icon(TCTGWindow.error_ico if error else TCTGWindow.ok_ico)
        if error:
            self.UnHide()

    def log(self, txts):
        print(*txts, sep="")
        self.logs.print(*txts)

    def show_infos(self, txts):
        self.tray.set_tooltip("".join(txts)[:128])
        self.infos.update(*txts)
        self.refresh()
        self.reappear()

    def ask_close(self):
        self.Hide()
        if widgets.YesNoWindow(**self.yes_no_kw).loop():
            return True
        self.UnHide()
        return False

    def loop(self):
        super().loop()
        self.tctg.stop()
        self.tray.close()
        self.close()
