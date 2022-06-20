import tkinter

import PySimpleGUI as sg

from .style import Style


class Window(sg.Window):
    _kwargs = dict(
        grab_anywhere=True,
        no_titlebar=True,
        debugger_enabled=False,
        keep_on_top=True,
        finalize=True,
    )
    _frame_kwargs = dict(
        p=0, border_width=1, relief=sg.RELIEF_SOLID, expand_x=True, expand_y=True
    )

    def __init__(self, title, layout, event_to_action=None, **kwargs):
        self.running = True
        self.event_to_action = event_to_action or {}
        args = title, [[sg.Frame("", layout, **Window._frame_kwargs)]]
        kwargs.update(Window._kwargs)
        super().__init__(*args, margins=(0, 0), **kwargs)

    # pylint: disable=invalid-name
    def Finalize(self, *args, **kwargs):
        super().Finalize(*args, **kwargs)
        for elt in self.element_list():
            elt.grab_anywhere_include()
            if hasattr(elt, "finalize"):
                elt.finalize()

    def write_event_value(self, key, value=None):
        if self.running:
            super().write_event_value(key, value)

    def loop(self):
        while True:
            event, values = self.read()
            if action := self.event_to_action.get(event):
                if action(values.get(event)):
                    self.running = False
                    return event


class YesNoWindow(Window):
    def __init__(self, title="", yes=None, no=None, font=None):
        yes, yes_color = yes or ("yes", None)
        no, no_color = no or ("no", None)
        width = max(len(yes), len(no)) * 4
        yes, no = f"{yes.capitalize():^{width//2}}", f"{no.capitalize():^{width}}"
        super().__init__(
            "",
            [
                [sg.T(title, font=font, expand_x=True, justification="center")],
                [
                    ButtonMouseOver(no, over_color=no_color, font=font),
                    sg.P(),
                    ButtonMouseOver(yes, over_color=yes_color, font=font),
                ],
            ],
            element_padding=(7, 7),
            event_to_action={yes: lambda _: True, no: lambda _: True},
        )
        self.yes = yes

    def loop(self):
        yes = super().loop() == self.yes
        self.close()
        return yes


class Splash:
    def __init__(self, img_data):
        self.window = Window("", [[sg.Image(data=img_data)]])
        self.window.refresh()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.window.close()


class ButtonMouseOver(sg.Button):
    binds = ("<Enter>", "<Leave>")

    def __init__(self, *args, over_color=None, **kwargs):
        self.current_color = None
        self.colors = dict(
            Enter=over_color if over_color else sg.theme_background_color(),
            Leave=kwargs.get("button_color") or sg.theme_button_color(),
        )
        super().__init__(*args, **kwargs)

    def finalize(self):
        for bind in ButtonMouseOver.binds:
            self.Widget.bind(bind, self._on_mouse_over)
        self.block_focus(True)

    def update(self, *args, **kwargs):
        kwargs["button_color"] = (
            self.colors["Leave"] if kwargs.get("disabled") else self.current_color
        )
        super().update(*args, **kwargs)

    def _on_mouse_over(self, event):
        self.current_color = self.colors.get(event.type.name)
        if not self.Disabled:
            self.update()


class ButtonCooldown(ButtonMouseOver):
    def __init__(self, *args, cooldown=100, **kwargs):
        self.cooldown = cooldown  # ms
        super().__init__(*args, **kwargs)

    def ButtonCallBack(self):
        super().ButtonCallBack()
        self.update(disabled=True)
        self.ParentForm.TKroot.after(self.cooldown, lambda: self.update(disabled=False))


def _from_style(element, txt):
    if isinstance(txt, Style):
        font, color = txt.get(element.Font)
        if color:
            if color == "transparent":
                color = element.BackgroundColor
            try:
                element.widget.winfo_rgb(color)
            except tkinter.TclError as err:
                msg = f"Style({txt=}, {font=}, {color=}) bad color"
                raise AttributeError(msg) from err
        return font, color

    return element.Font, None


class MLineColors(sg.MLine):
    def __init__(self, *args, colors=None, **kwargs):
        self.colors = colors or {}
        super().__init__(*args, **kwargs)

    def print_style(self, txt="", end="\n"):
        font, color = _from_style(self, txt)
        super().print(txt, font=font, t=self.colors.get(color, color), end=end)
        return font

    # pylint: disable=unused-argument
    def print(self, *args, **kwargs):
        for txt in args:
            self.print_style(txt, end="")
        self.print_style()

    def grab_anywhere_include(self):
        super().grab_anywhere_include()
        # selection bg = bg and normal mouse cursor
        widget = self.widget
        widget.configure(selectbackground=widget.cget("bg"), cursor="arrow")


class MLineAutoSize(sg.Frame):
    _kwargs = dict(
        border_width=0,
        no_scrollbar=True,
        auto_refresh=False,
        write_only=True,
        disabled=True,
        expand_x=True,
        expand_y=True,
    )

    def __init__(self, *args, pad=0, colors=None, **kwargs):
        kwargs.update(MLineAutoSize._kwargs)
        self.mline = MLineColors(*args, colors=colors, **kwargs)
        super().__init__(
            "",
            [[self.mline]],
            border_width=0,
            pad=pad,
            expand_x=True,
            expand_y=True,
        )

    def _print_row(self, row):
        w_row, h_row = 0, 0
        for txt in row:
            font = self.mline.print_style(txt, end="")
            wfont = tkinter.font.Font(self.ParentForm.TKroot, font)
            w_row += wfont.measure(txt)
            h_row = max(h_row, wfont.metrics("linespace"))

        return w_row, h_row

    def _resize(self, width, height):
        pad = self.mline.Pad or self.mline.ParentForm.ElementPadding
        padx, pady = (2 * (p + 1) for p in pad)
        widget = self.widget
        widget.pack_propagate(0)
        widget.config(width=width + padx, height=height + pady)

    @staticmethod
    def _get_rows(txts):
        row = []
        for txt in txts:
            txt = txt.splitlines(True)
            row.append(txt[0])
            if txt[0] == "\n" or len(txt) > 1:
                yield row
                row = txt[1:]

        if row:
            yield row

    def update(self, *txts):
        self.mline("")

        row = None
        width, height = 0, 0
        for row in self._get_rows(txts):
            w_row, h_row = self._print_row(row)
            width = max(width, w_row)
            height += h_row

        if row and row[-1] == "\n":
            height += h_row

        self._resize(width, height)


class TextColor(sg.T):
    def __init__(self, *args, colors=None, **kwargs):
        self.colors = colors or {}
        super().__init__(*args, **kwargs)

    def update(self, *args, **kwargs):
        font, color = _from_style(self, args[0])
        color = self.colors.get(color, color)
        kwargs["text_color"] = color or kwargs.get("text_color")
        kwargs["font"] = font
        super().update(*args, **kwargs)


class AnimatedTxt(TextColor):
    def __init__(self, *args, dt=125, pattern="••", length=6, **kwargs):
        self._pattern = pattern
        self._length = length
        self._dt = dt
        self._index = 0
        self._animated = False
        super().__init__(*args, **kwargs)

    def update(self, *args, animated=False, **kwargs):
        super().update(*args, **kwargs)
        if animated != self._animated:
            self._index = 0
            self._animated = animated
            self._animate(args[0], **kwargs)

    def _get_anim(self):
        i = self._index % (self._length * 2)
        i = i if i <= self._length else (self._length * 2 - i)
        self._index += 1
        return " " * i + self._pattern

    def _animate(self, txt, **kwargs):
        if self._animated:
            super().update(txt + self._get_anim(), **kwargs)
            self.ParentForm.TKroot.after(self._dt, lambda: self._animate(txt, **kwargs))
