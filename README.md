# Cloud Infrastructure Agent

This project implements a **Cloud Infrastructure Assessment Agent**. It uses a backbone of
LLM-powered metric evaluators combined with an orchestrator layer and workflows to compute
a weighted overall score for cloud environments.

The agent can run individual or multiple metrics, automatically resolve dependencies,
and produce structured outputs validated against schemas. Final reports are saved to JSON
for traceability and analysis.

---

## 📐 Architecture

The repo is organized into three layers:

- **`agent_layer/`** — Orchestrator layer
  - Metric registry (`registry.py`)
  - Schemas & validation (`schemas.py`, `validate.py`)
  - Loader for backbone metric functions (`tool_loader.py`)
  - Router (`router.py`)

- **`cloud_infra_agent/`** — Backbone layer
  - Implements the actual metric scoring logic (`metrics.py`)
  - Utilities for calling LLMs (`call_llm_.py`, `base_agents.py`)
  - Sample input/output data (`Data/Sample2/inputs`)

- **`workflows/`** — Assembly layer
  - Defines workflows that tie metrics together, e.g. `monitor_workflow.py`

- **`app/`** — API layer
  - FastAPI application (`main.py`) to expose the agent over HTTP

---

## ⚙️ Setup

1. **Python Version**
   - Requires Python 3.9+ (tested on 3.11/3.12).

2. **Clone & Install**
   ```bash
   git clone <this-repo>
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. # ===============================
# Cloud Infrastructure Agent ENV
# ===============================
CLOUD_INFRA_DATA_DIR=cloud_infra_agent/Data
LLM_PROVIDER=openai          # options: openai | google

OPENAI_API_KEY=sk-proj-xxxxxxx   # put your real key here
OPENAI_MODEL=gpt-4o-mini         # e.g. gpt-4o-mini, gpt-4-turbo

GOOGLE_GENAI_USE_VERTEXAI=FALSE  # set TRUE if using Vertex AI
GOOGLE_API_KEY=                  # your Google Generative AI API key
GOOGLE_MODEL=gemini-1.5-flash    # e.g. gemini-1.5-flash, gemini-pro

# --- Backbone ---
# Where to import metric functions from
# Example: cloud_infra_agent.agent_wrappers
BACKBONE_MODULE=cloud_infra_agent.agent_wrappers

DEFAULT_PLATFORM=aws             # aws | azure | gcp



---

## 🚀 Usage

### Run via FastAPI

Start the server:
```bash
uvicorn agent.app.main:app --reload
```

### Inputs

cfg = {
    "metrics": "all",                   # or a list like ["score_compute_utilization"]
    "output_path": "./runs/result.json" # optional; default is ./runs/run-<ts>.json
}
ctx = {
    "score_compute_utilization": {"params": {"cpu": 0.7}},
    # other per-metric params can go here
}


---

## 🎯 Metric Selection

- **All metrics (default)**  
  `config["metrics"] = "all"` or omit the key.

- **Single metric (L0)**  
  `config["metrics"] = "score_compute_utilization"`

- **Dependent metric (L1)**  
  `config["metrics"] = ["score_cost_allocation_quality"]`  
  → automatically includes `score_tagging_coverage` as its dependency.

- **Multiple metrics**  
  `config["metrics"] = ["score_k8s_utilization", "score_autoscaling_effectiveness"]`

---

## 🎯 Metric Input Modes

Each metric can be provided inputs in three ways:

- **ADirect Parameters (params)** 

  ctx = {
    "score_compute_utilization": {
      "params": {"cpu": 0.7, "memory": 0.5}
    }
  }


- **ASample Data (sample_name)** 

  ctx = {
    "score_compute_utilization": {
      "sample_name": "Sample3"
    }
  }


→ loads cloud_infra_agent/Data/Sample3/inputs/compute.utilization.json

- **AFallback (Default Sample)** 

  ctx = {}


  → defaults to "Sample2"


## 💾 JSON Output

- By default, results are saved under `./runs/run-<timestamp>.json`
- Or specify your own file with `config["output_path"]`

Example saved file:
```json
{
  "metrics": {
    "score_compute_utilization": {...},
    "score_k8s_utilization": {...}
  },
  "summary": {
    "overall_score": 3.7,
    "category_scores": {"cost": 3.2, "efficiency": 4.1, ...}
  }
}
```

---

## 📊 Data & Samples

Sample inputs are stored in `cloud_infra_agent/Data/Sample2/inputs/`.

Each metric has a JSON input file, e.g.:
- `compute_utilization.json`
- `security_iam_risk.json`

These can be used for testing the workflow without live data.


## 📂 Directory Structure

```

  ├── agent_layer/       # Orchestrator (schemas, registry, loader, validate)
  ├── app/               # FastAPI entrypoint
  ├── cloud_infra_agent/ # Backbone (metrics, LLM calls, data)
  ├── workflows/         # Workflow definitions
  └── README.md          # This file
```

