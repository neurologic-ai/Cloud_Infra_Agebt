# CloudInfraAgent

**CloudInfraAgent** is a modular framework for assessing cloud infrastructure across **FinOps, security, scaling, availability, and utilization**.  
It ingests JSON inputs, an **LLM** for consistent scoring (1–5).  


---

## 📂 Project Structure

```
cloud_infra_agent/
├── main.py                  # Entry point for running agent
├── base_agents.py           # Base classes for agent orchestration     
├── call_llm_.py             # LLM call wrappers
├── compute_functions.py     # Functions for metric computation
├── config.py                # Configurations and constants
├── metric_input_loader.py   # Load JSON inputs for metrics
├── metrics.py               # Metric registry and prompts
├── utility_functions.py     # Shared helpers (aggregation, scoring, utils)
└── Data/
    └── Sample2/
        ├── inputs/          # Input JSONs per metric
        └── output.json      # Generated output
```

---

## 🚀 Features

- **Multi-domain Metric Coverage**  
  - Tagging coverage  
  - Compute utilization  
  - Database and load balancer metrics  
  - Kubernetes efficiency  
  - Scaling effectiveness  
  - Cost allocation, idle/waste tracking  
  - IAM risks, vulnerabilities, CSPM findings  

- **LLM Scoring**  
  **LLM-powered reasoning** for structured outputs.

- **Pluggable Design**  
  Add new metrics by extending `DEFAULT_METRICS` in `config.py` and mapping them in `metrics.py`.

- **Sample Datasets**  
  Ready-to-run JSONs included in `Data/Sample2/inputs`.

---

## ⚙️ Installation

```bash
git clone <your-repo-url>
python3 -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Set environment variables (via `.env`):

```env
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY=your-google-key
OPENAI_KEY=your-openai-key
CLOUD_INFRA_DATA_DIR=cloud_infra_agent/Data
```

---

## ▶️ Usage

### Run with Sample Data

```bash
python -m cloud_infra_agent.main <sample_data_folder_name>
```

This will:
1. Load mappings from `Data/<sample_data_folder_name>/inputs/`
2. Ccall LLM for scoring
3. Generate structured output (`output.json`)


---

## 📊 Example Input → Output

### Input (`Data/Sample2/inputs/tagging_coverage.json`)

```json
{
  "resources": [
    {"id": "i-0a1b2c", "tags": {"env": "prod", "owner": "ml-team"}}
  ],
  "required_tags": ["env", "owner", "cost-center", "service"]
}
```

### LLM Evaluation Output

```json
{
  "metric_id": "tagging.coverage",
  "score": 3,
  "rationale": "85% resources have required tags."
}
```

