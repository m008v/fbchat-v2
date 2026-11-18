"""Generate the public namespace for builds without tracking duplicate sources."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, object]) -> None:
        root = Path(self.root)
        script = root / "scripts" / "sync_canonical_package.py"
        if not script.is_file():
            # A published sdist already contains the generated src/fbchat_v2 tree.
            if not (root / "src" / "fbchat_v2" / "__init__.py").is_file():
                raise RuntimeError(
                    "Neither source generator nor packaged sources exist"
                )
            return
        spec = importlib.util.spec_from_file_location("_fbchat_package_build", script)
        if spec is None or spec.loader is None:
            raise RuntimeError("Cannot load the package generator")
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)
        snapshot = generator.expected_snapshot()
        generator.sync_snapshot(snapshot)
        differences = generator.snapshot_differences(snapshot)
        if differences:
            raise RuntimeError("Generated package does not match its source allowlist")
        if self.target_name == "wheel" and version == "editable":
            return  # The editable wheel points at build/ and src/ using a .pth file.
        prefix = "src" if self.target_name == "sdist" else ""
        build_data["force_include"] = {
            str(path): str(
                Path(prefix) / path.relative_to(generator.TARGET_ROOT.parent)
            )
            for path in snapshot
        }
