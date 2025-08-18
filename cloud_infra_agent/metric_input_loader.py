# metric_input_loader.py
import json
from pathlib import Path
from typing import Dict, Any

DEFAULT_BASE_DIR = "cloud_infra_agent/inputs"

def load_metric_inputs(map_file: str, base_dir: str = DEFAULT_BASE_DIR) -> Dict[str, Any]:
    """
    Load all inputs according to the metric_id → filename map.

    Args:
        map_file: Path to the JSON file containing {metric_id: filename}.
        base_dir: Directory prefix where input files live (defaults to 'inputs').

    Returns:
        Dict[str, Any]: { metric_id: input_json_data }
    """
    map_path = Path(map_file)
    mapping = json.loads(map_path.read_text(encoding="utf-8"))
    result: Dict[str, Any] = {}

    for metric_id, filename in mapping.items():
        fpath = Path(base_dir) / filename
        try:
            data = json.loads(fpath.read_text(encoding="utf-8"))
        except Exception as e:
            raise RuntimeError(f"Failed loading {filename} for {metric_id}: {e}")
        result[metric_id] = data

    return result


def load_metric_input(map_file: str, metric_id: str, base_dir: str = DEFAULT_BASE_DIR) -> Any:
    """
    Load a single metric's input using the same {metric_id: filename} map.

    Args:
        map_file: Path to the JSON file containing {metric_id: filename}.
        metric_id: The metric id to load input for.
        base_dir: Directory prefix where input files live (defaults to 'inputs').

    Returns:
        The parsed JSON payload for the metric_id.

    Raises:
        KeyError if metric_id not found in the map.
        RuntimeError if file read/parse fails.
    """
    map_path = Path(map_file)
    mapping = json.loads(map_path.read_text(encoding="utf-8"))

    if metric_id not in mapping:
        raise KeyError(f"metric_id '{metric_id}' not found in {map_file}")

    fpath = Path(base_dir) / mapping[metric_id]
    try:
        return json.loads(fpath.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"Failed loading {mapping[metric_id]} for {metric_id}: {e}")


# # example usage
# if __name__ == "__main__":
#     # assumes you have map.json and inputs/tagging_coverage.json etc.
#     all_inputs = load_metric_inputs("map.json")
#     print(all_inputs["tagging.coverage"])  # → dict with resources + required_tags

#     single = load_metric_input("map.json", "tagging.coverage")
#     print(single)
