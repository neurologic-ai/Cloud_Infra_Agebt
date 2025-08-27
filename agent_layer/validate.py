from __future__ import annotations
from typing import Any, Callable, Dict
from pydantic import ValidationError
from uuid import uuid4
import os

from .schemas import MetricInput, MetricOutput, Category, Finding
from . import registry

DEFAULT_PLATFORM = os.getenv("DEFAULT_PLATFORM", "aws")

# Build a metric_name -> Category map from registry.CATEGORIES to avoid duplication
def _metric_name_to_category() -> Dict[str, Category]:
    mapping: Dict[str, Category] = {}
    cats = getattr(registry, "CATEGORIES", {})
    for cat_name, meta in cats.items():
        metrics = (meta or {}).get("metrics", {}) or {}
        for m in metrics.keys():
            try:
                mapping[m] = Category(cat_name)  # will raise if unknown
            except Exception:
                # default if unknown category label
                mapping[m] = Category.efficiency
    return mapping

_NAME_TO_CATEGORY = _metric_name_to_category()

def _coerce_input_to_metric_input(metric_name: str, raw_ctx: Dict[str, Any]) -> MetricInput:
    if not isinstance(raw_ctx, dict):
        raw_ctx = {}

    # Pull params/deps from legacy shapes; otherwise treat non-decor keys as params
    if "params" in raw_ctx and isinstance(raw_ctx["params"], dict):
        params = dict(raw_ctx["params"])
    else:
        params = {k: v for k, v in raw_ctx.items() if k not in ("deps", "run_id", "platform", "sample_name")}

    deps = raw_ctx.get("deps")
    if not isinstance(deps, dict):
        deps = None

    platform = raw_ctx.get("platform") or DEFAULT_PLATFORM
    run_id = raw_ctx.get("run_id") or f"run-{uuid4()}"

    context: Dict[str, Any] = dict(params or {})
    if deps is not None:
        context["deps"] = deps

    return MetricInput(run_id=run_id, platform=platform, context=context)

def _coerce_score(score: Any) -> Any:
    if not isinstance(score, (int, float)):
        return score
    return float(score)  # expect 0–5 directly


def _finalize_output(metric_name: str, m_in: MetricInput, out: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(out or {})
    out.setdefault("metric_id", metric_name)
    out.setdefault("platform", m_in.platform)
    if "category" not in out:
        out["category"] = _NAME_TO_CATEGORY.get(metric_name, Category.efficiency)

    if "score" in out:
        out["score"] = _coerce_score(out["score"])

    out.setdefault("confidence", 0.8)

    findings = out.get("findings", [])
    norm_findings = []
    if isinstance(findings, list):
        for f in findings:
            if isinstance(f, Finding):
                norm_findings.append(f)
            elif isinstance(f, dict):
                norm_findings.append(f)
            elif isinstance(f, str):
                norm_findings.append({"key": f, "message": f})
    out["findings"] = norm_findings

    if "evidence_refs" not in out or out["evidence_refs"] is None:
        out["evidence_refs"] = []

    return out

def make_validated_metric(fn: Callable[..., Dict[str, Any]], metric_name: str) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    """
    Wrap a backbone metric function so that:
      - Input is validated/coerced to notebook-style MetricInput
      - Output is coerced/validated to notebook-style MetricOutput
      - Failures become standardized MetricOutput with score=0.0
      - Backward-compatible call into backbone using {"params":..., "deps":...}
    """
    def _wrapped(raw_ctx: Dict[str, Any]) -> Dict[str, Any]:
        # INPUT VALIDATION
        try:
            m_in = _coerce_input_to_metric_input(metric_name, raw_ctx if isinstance(raw_ctx, dict) else {})
        except ValidationError as ve:
            return MetricOutput(
                metric_id=metric_name,
                category=_NAME_TO_CATEGORY.get(metric_name, Category.efficiency),
                platform=(raw_ctx.get("platform") if isinstance(raw_ctx, dict) else None) or DEFAULT_PLATFORM,
                score=0.0,
                confidence=0.0,
                rationale=f"Input validation error: {ve.errors()}",
                findings=[],
                evidence_refs=[],
            ).model_dump()

        # CALL BACKBONE with legacy shape
        orig_params = raw_ctx.get("params") if isinstance(raw_ctx, dict) else None
        orig_sample = raw_ctx.get("sample_name") if isinstance(raw_ctx, dict) else None

        call_ctx: Dict[str, Any] = {}

        if isinstance(orig_params, dict) and orig_params:
            # user explicitly provided params → pass them through
            call_ctx["params"] = dict(orig_params)
        elif isinstance(orig_sample, str) and orig_sample:
            # user explicitly requested a sample → let backbone load it
            call_ctx["sample_name"] = orig_sample
        elif m_in.context:
            # flat inputs provided (not named params/sample_name) → treat as params (exclude deps)
            call_ctx["params"] = {k: v for k, v in m_in.context.items() if k != "deps"}
        # always append deps if present
        if "deps" in m_in.context:
            call_ctx["deps"] = m_in.context["deps"]

        try:
            out = fn(call_ctx) or {}
        except Exception as e:
            return MetricOutput(
                metric_id=metric_name,
                category=_NAME_TO_CATEGORY.get(metric_name, Category.efficiency),
                platform=m_in.platform,
                score=0.0,
                confidence=0.0,
                rationale=f"Exception inside metric: {e}",
                findings=[],
                evidence_refs=[],
            ).model_dump()

        # OUTPUT VALIDATION
        try:
            coerced = _finalize_output(metric_name, m_in, out)
            m_out = MetricOutput.model_validate(coerced)
            return m_out.model_dump()
        except ValidationError as ve:
            return MetricOutput(
                metric_id=metric_name,
                category=_NAME_TO_CATEGORY.get(metric_name, Category.efficiency),
                platform=m_in.platform,
                score=0.0,
                confidence=0.0,
                rationale=f"Output validation error: {ve.errors()}",
                findings=[],
                evidence_refs=[],
            ).model_dump()

    return _wrapped
