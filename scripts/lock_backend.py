"""Capture installed dependency closures without local editable paths."""
from importlib.metadata import distribution, distributions
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def lock(roots: list[str], target: str) -> None:
    pending = roots.copy()
    packages: dict[str, str] = {}
    while pending:
        name = canonicalize_name(pending.pop())
        if name in packages:
            continue
        package = distribution(name)
        packages[name] = package.version
        for raw in package.requires or []:
            requirement = Requirement(raw)
            if requirement.marker is None or requirement.marker.evaluate():
                pending.append(requirement.name)
    Path(target).write_text(
        "# Generated from the tested Python 3.12 environment.\n"
        + "\n".join(f"{name}=={version}" for name, version in sorted(packages.items()))
        + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    runtime = ["fastapi", "uvicorn", "httpx", "pypdf", "python-multipart", "rdkit"]
    lock(runtime, "backend/requirements.lock")
    development = [
        item.metadata["Name"] for item in distributions()
        if canonicalize_name(item.metadata["Name"]) not in {"pip", "setuptools", "baylab-backend"}
    ]
    lock(development, "backend/requirements-dev.lock")
