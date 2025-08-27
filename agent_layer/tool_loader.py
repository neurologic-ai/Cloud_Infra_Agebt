import importlib
import os
from typing import Callable, Any
import pkgutil

from agent_layer.validate import make_validated_metric

# point to your wrappers module (module path, NOT file path)
BACKBONE_MODULE = os.getenv("BACKBONE_MODULE", "cloud_infra_agent.agent_wrappers")

def load_function(func_name: str) -> Callable[..., Any]:
    base = importlib.import_module(BACKBONE_MODULE)

    # direct attribute
    if hasattr(base, func_name):
        fn = getattr(base, func_name)
        return make_validated_metric(fn, func_name)

    raise ImportError(f"{func_name} not found in {BACKBONE_MODULE}")
