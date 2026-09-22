# -*- coding: utf-8 -*-
"""Lazy loading screen manager for RetroHub.

Avoids importing and instantiating all 17+ screen controllers at startup,
saving significant CPU and SD card I/O on handheld devices.
"""

import importlib


class LazyScreenMap(dict):
    """Dictionary mapping screen names to Screen instances with on-demand lazy instantiation.
    Avoids importing and constructing heavy screen controllers at application startup.
    """

    def __init__(self, engine=None):
        super().__init__()
        self.engine = engine
        self._factories = {}

    def register_lazy(self, name, module_name, class_name):
        """Register a screen to be imported and instantiated on first access."""
        self._factories[name] = (module_name, class_name)

    def __contains__(self, name):
        return super().__contains__(name) or (name in self._factories)

    def __getitem__(self, name):
        if name in self._factories and not super().__contains__(name):
            self._instantiate(name)
        if super().__contains__(name):
            return super().__getitem__(name)
        raise KeyError(name)

    def get(self, name, default=None):
        try:
            if name in self:
                return self[name]
        except Exception:
            pass
        return default

    def _instantiate(self, name):
        mod_name, cls_name = self._factories[name]
        mod = importlib.import_module(mod_name)
        cls = getattr(mod, cls_name)
        instance = cls(self.engine)
        instance.engine = self.engine
        super().__setitem__(name, instance)
        return instance

    def keys(self):
        return set(super().keys()).union(self._factories.keys())

    def values(self):
        return [self[k] for k in self.keys()]

    def items(self):
        return [(k, self[k]) for k in self.keys()]
