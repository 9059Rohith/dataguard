"""Regenerate exact runtime/dev versions from this verified Python environment."""

from importlib.metadata import distribution, distributions
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

roots = ["fastapi", "uvicorn", "sqlalchemy", "psycopg[binary]", "prometheus-client"]
versions = {}
queue = [Requirement(value) for value in roots]
while queue:
    requirement = queue.pop()
    name = canonicalize_name(requirement.name)
    if name in versions:
        continue
    package = distribution(name)
    versions[name] = package.version
    for value in package.requires or []:
        child = Requirement(value)
        if child.marker is None or any(
            child.marker.evaluate({"extra": extra}) for extra in ["", *requirement.extras]
        ):
            queue.append(child)
header = "# Exact versions verified 2026-10-30; regenerate with python scripts/lock.py\n"
Path("requirements.lock").write_text(
    header + "".join(f"{n}=={v}\n" for n, v in sorted(versions.items())), encoding="utf-8"
)
dev = {
    canonicalize_name(d.metadata["Name"]): d.version
    for d in distributions()
    if canonicalize_name(d.metadata["Name"]) not in {"dataguard-reliability", "pip", "setuptools"}
}
Path("requirements-dev.lock").write_text(
    header + "".join(f"{n}=={v}\n" for n, v in sorted(dev.items())), encoding="utf-8"
)
