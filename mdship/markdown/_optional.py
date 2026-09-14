"""Optional third-party and stdlib imports, bound to None when unavailable."""

try:
    import yaml
except ImportError:
    yaml = None

try:
    import json
except ImportError:
    json = None

try:
    import tomllib
except ImportError:
    tomllib = None

try:
    import toml
except ImportError:
    toml = None

try:
    import xml.etree.ElementTree as ET
except ImportError:
    ET = None
