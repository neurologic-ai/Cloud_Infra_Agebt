from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional
from enum import Enum
from pydantic import BaseModel, Field, field_validator

class Category(str, Enum):
    cost = "cost"
    efficiency = "efficiency"
    reliability = "reliability"
    security = "security"

class MetricInput(BaseModel):
    run_id: str
    platform: Literal["aws", "azure", "gcp"]
    # Arbitrary inputs including deps for L1 go inside context
    context: Dict[str, Any] = Field(default_factory=dict)

class Finding(BaseModel):
    key: str
    severity: Literal["low","medium","high","critical"] = "low"
    message: str
    owner: Optional[str] = None
    system: Optional[str] = None

class MetricOutput(BaseModel):
    metric_id: str
    category: Category
    platform: Literal["aws", "azure", "gcp"]
    score: float = Field(ge=0.0, le=5.0)
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    rationale: str = ""
    findings: List[Finding] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)

    @field_validator("evidence_refs", mode="before")
    @classmethod
    def _coerce_evidence_refs(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return v
