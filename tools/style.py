class Style(str):
    # pylint: disable=super-init-not-called
    def __init__(self, _=""):
        # styles key order is important to have a working font
        self._styles = dict(bold=False, italic=False, underline=False)
        self._color = None
        self._dsize = 0

    def __call__(self, txt):
        """copy style of self"""
        txt = Style(txt)
        txt._styles = self._styles.copy()
        txt._color = self._color
        txt._dsize = self._dsize
        return txt

    def __add__(self, txt):
        """Style + str"""
        return self(str(self) + txt)

    def __radd__(self, txt):
        """str + Style"""
        return self(txt + str(self))

    def __getattribute__(self, name):
        attr = super().__getattribute__(name)
        # is it a str method ?
        if name in dir(str):

            def method(*args, **kwargs):
                """keep str methods returned values self style"""
                value = attr(*args, **kwargs)
                if isinstance(value, str):
                    return self(value)
                if isinstance(value, (list, tuple)):
                    return type(value)(map(self, value))
                return value

            return method

        return attr

    def bigger(self, delta=1):
        self._dsize += delta
        return self

    def smaller(self, delta=1):
        self._dsize -= delta
        return self

    def warn(self, cond):
        return self.red if cond else self.green

    def __getattr__(self, name):
        if name in self._styles:
            self._styles[name] = True
            return self
        return self.color(name)

    def color(self, color):
        self._color = color
        return self

    def font_color(self, font):
        font, size = font
        font += f" {size + self._dsize}"
        for style, enabled in self._styles.items():
            if enabled:
                font += f" {style}"
        return font, self._color
