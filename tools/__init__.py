"""
88888888888                   888
    888                       888
    888                       888
    888      .d88b.   .d88b.  888 .d8888b
    888     d88""88b d88""88b 888 88K
    888     888  888 888  888 888 "Y8888b.
    888     Y88..88P Y88..88P 888      X88
    888      "Y88P"   "Y88P"  888  88888P'
"""

import base64
import io
import re
from datetime import timedelta

from PIL import Image


def day_hour(date):
    return f"{date:%d/%m/%y}", f"{date:%Hh%M:%S}"


def img_to64(path, height=None):
    im = Image.open(path)
    if height:
        width = round(im.size[0] * height / im.size[1])
        im.thumbnail((width, height))
    buffer = io.BytesIO()
    im.save(buffer, "PNG")
    return base64.b64encode(buffer.getvalue())


def plural(txt, n):
    try:
        return f'{txt}{"s" if float(n) > 1 else ""}'
    except ValueError:
        return txt


def timedelta_loc(dt):
    values = re.findall(r"(\d+)", f"{timedelta(seconds=round(dt.total_seconds()))}")
    units = ["jour", "heure", "minute", "seconde"]
    return ", ".join(
        f"{v} {plural(unit, v)}"
        for value, unit in zip(values, units[4 - len(values) :])
        if (v := int(value)) != 0
    )


def seconds_left_loc(seconds):
    txt = f"{timedelta(seconds=round(seconds))}"
    return txt.replace(":", "h", 1).replace("day", "jour")


def number(number_str):
    try:
        number_ = float(number_str)
        for thousand in f"{number_:,}".split(","):
            if "." in thousand:
                thousand, decimals = thousand.split(".")
                yield number_str(thousand)
                if decimals != "0":
                    yield number_str(f".{decimals}").smaller(2)
            else:
                yield number_str(thousand)
                yield number_str(" ").smaller(2)

    except ValueError:
        yield number_str
