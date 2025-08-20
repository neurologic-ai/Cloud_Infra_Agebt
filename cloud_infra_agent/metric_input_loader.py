from pathlib import Path
from typing import Any, Dict
import json

from cloud_infra_agent.config import Input_File_For_Metric_map


def load_metric_input(
    sample_name: str,
    metric_id: str,
    base_dir: Path,
    mapping: Dict[str, str] = Input_File_For_Metric_map
) -> Any:
    """
    Load a single metric's input using the {metric_id: filename} map for a given sample.

    Directory layout assumed:
      cloud_infra_agent/Data/<sample_name>/
        ├─ inputs/
        │   ├─ <files referenced in map_file>
        └─ <map_file>   (e.g., metric_input_map.json)

    Args:
        sample_name: Folder under Data/ (e.g., "Sample1").
        map_file: Filename or absolute path to the JSON mapping {metric_id: filename}.
        metric_id: The metric id to load input for.
        base_dir: Root directory that contains the sample folders (defaults to cloud_infra_agent/Data).

    Returns:
        The parsed JSON payload for the metric_id.
    """
    sample_root = Path(base_dir) / sample_name
    inputs_dir = sample_root / "inputs"

    if not inputs_dir.exists():
        raise FileNotFoundError(f"Inputs directory not found: {inputs_dir}")

    if metric_id not in mapping:
        available = ", ".join(sorted(mapping.keys()))
        raise KeyError(f"metric_id '{metric_id}' not found in InputFile Name Map. Available: {available}")

    fpath = inputs_dir / mapping[metric_id]
    if not fpath.exists():
        raise FileNotFoundError(f"Input file for '{metric_id}' not found: {fpath}")

    try:
        return json.loads(fpath.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"Failed loading {fpath.name} for {metric_id}: {e}")



# # example usage
# if __name__ == "__main__":
#     # assumes you have map.json and inputs/tagging_coverage.json etc.
#     all_inputs = load_metric_inputs("map.json")
#     print(all_inputs["tagging.coverage"])  # → dict with resources + required_tags

#     single = load_metric_input("map.json", "tagging.coverage")
#     print(single)
