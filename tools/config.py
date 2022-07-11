from types import SimpleNamespace

from .loader import Loader, YamlLoader


class Config(SimpleNamespace, YamlLoader):
    """nested SimpleNamespace that can be loaded and saved"""

    _to_obj = lambda a_dict: Config(
        **{
            k: Config._to_obj(v) if isinstance(v, dict) else v
            for k, v in a_dict.items()
        }
    )
    _to_dict = lambda obj: {
        k: Config._to_dict(v) if isinstance(v, Config) else v
        for k, v in obj.__dict__.items()
    }

    _yaml_load = lambda loader, node, cls: Config._to_obj(
        loader.construct_mapping(node, deep=True)
    )
    _yaml_save = lambda dumper, data, tag: dumper.represent_mapping(
        tag, Config._to_dict(data)
    )


class LoaderConfig:
    """behave like a Config object that's loaded at init and can be saved"""

    def __init__(self, filename):
        self._loader = Loader(filename)
        self._config = self._loader.load()

    def __getattr__(self, name):
        return getattr(self._config, name)

    def __setattr__(self, name, value):
        if name in ("_loader", "_config"):
            super().__setattr__(name, value)
        elif hasattr(self._config, name):
            setattr(self._config, name, value)
        else:
            raise AttributeError

    def save(self):
        self._loader.save(self._config)
