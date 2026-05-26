import sys
from pathlib import Path

import pytest


SRC_ROOT = Path(__file__).resolve().parents[1]

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def _derive_feature_from_nodeid(nodeid: str) -> str:
    """Infer a feature label from a pytest node id path."""
    file_part = nodeid.split("::", 1)[0].replace("\\", "/")
    base = file_part.rsplit("/", 1)[-1]
    if base.startswith("test_"):
        base = base[len("test_"):]
    if base.endswith(".py"):
        base = base[:-3]
    return base.replace("_", "-")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Attach feature metadata to every test for traceable coverage reports."""
    for item in items:
        marker = item.get_closest_marker("feature")
        feature = str(marker.args[0]) if marker and marker.args else _derive_feature_from_nodeid(item.nodeid)
        if marker is None:
            item.add_marker(pytest.mark.feature(feature))
        item.user_properties.append(("feature", feature))