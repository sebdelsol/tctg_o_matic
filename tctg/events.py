from enum import Enum

Events = Enum(
    "Event",
    (
        "log",
        "show_infos",
        "set_tray_icon",
        "log_left",
        "updating",
        "enable_update",
        "update",
        "minimize",
        "unhide",
        "close",
        "logo",
    ),
)
