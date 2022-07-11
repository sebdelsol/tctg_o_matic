import os
from functools import partial

import yaml

# dump without aliases to avoid shared objects at loading
yaml.SafeDumper.ignore_aliases = lambda *args: True


class YamlLoader:
    """register at class declaration a constructor and a representer for yaml"""

    _yaml_load = None
    _yaml_save = None

    def __init_subclass__(cls, register=True, **kwargs):
        super().__init_subclass__(**kwargs)
        if register:
            tag = f"!{cls.__name__}"
            yaml.SafeLoader.add_constructor(tag, partial(cls._yaml_load, cls=cls))
            yaml.SafeDumper.add_representer(cls, partial(cls._yaml_save, tag=tag))


class YamlMapping(YamlLoader, register=False):
    """inherit for loading & saving dataclass or dict"""

    _yaml_load = lambda loader, node, cls: cls(**loader.construct_mapping(node))
    _yaml_save = lambda dumper, data, tag: dumper.represent_mapping(tag, data.__dict__)


class YamlSequence(YamlLoader, register=False):
    """inherit for loading & saving list"""

    _yaml_load = lambda loader, node, cls: cls(loader.construct_sequence(node))
    _yaml_save = lambda dumper, data, tag: dumper.represent_sequence(tag, data)


class Loader:
    """safe yaml loader & dumper"""

    def __init__(self, filename):
        self.filename = filename

    def load(self):
        if os.path.exists(self.filename):
            with open(self.filename, "r", encoding="utf8") as f:
                return yaml.safe_load(f)
        return None

    def save(self, obj):
        with open(self.filename, "w", encoding="utf8") as f:
            yaml.safe_dump(obj, f, allow_unicode=True, sort_keys=False)
