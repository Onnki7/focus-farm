import json, os
_settings = None

def load():
    global _settings
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(base, "config.json")) as f:
        _settings = json.load(f)
    return _settings

def get(key, default=None):
    if _settings is None:
        load()
    return _settings.get(key, default)
