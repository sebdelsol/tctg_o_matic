from types import SimpleNamespace

_events = (
    "log",
    "show_infos",
    "set_error",
    "log_left",
    "updating",
    "enable_update",
    "update",
    "minimize",
    "close",
    "timeout",
    "logo",
)

Events = SimpleNamespace(**{event: f"__{event}__" for event in _events})
