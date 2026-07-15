from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

import importlib.util
import inspect
import os
from pathlib import Path
from types import ModuleType
from typing import Optional

from .base import GraphNode
from .registry import register_node


DEFAULT_CUSTOM_NODE_PATH = Path(__file__).resolve().parent.parent / 'custom_nodes'


def _load_module(path: Path) -> Optional[ModuleType]:
    try:
        module_name = f'eeg_app.custom_nodes.{path.stem}'
        spec = importlib.util.spec_from_file_location(module_name, str(path))
        if not spec or not spec.loader:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as exc:
        logger.debug(f'[GraphNodes] Failed to load custom node module {path}: {exc}')
        return None


def load_custom_nodes(custom_path: Optional[str] = None) -> Path:
    path = Path(custom_path or os.getenv('EEG_CUSTOM_NODE_PATH') or DEFAULT_CUSTOM_NODE_PATH)
    path.mkdir(parents=True, exist_ok=True)

    for file in sorted(path.glob('*.py')):
        if file.name.startswith('_'):
            continue
        module = _load_module(file)
        if not module:
            continue

        if hasattr(module, 'register_custom_nodes'):
            try:
                module.register_custom_nodes(register_node)
            except Exception as exc:
                logger.debug(f'[GraphNodes] register_custom_nodes failed in {file}: {exc}')
            continue

        for _, member in inspect.getmembers(module, inspect.isclass):
            if not issubclass(member, GraphNode) or member is GraphNode:
                continue
            try:
                register_node(member)
            except Exception as exc:
                logger.debug(f'[GraphNodes] Failed to register class {member.__name__} from {file}: {exc}')

    return path
