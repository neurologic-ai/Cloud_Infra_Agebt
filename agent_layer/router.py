from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any
from workflows.monitor_workflow import run_workflow

router = APIRouter()

class WorkflowRunRequest(BaseModel):
    config: Dict[str, Any] = {}
    context: Dict[str, Any] = {}

@router.post("/run_workflow")
def run_workflow_endpoint(req: WorkflowRunRequest):
    return run_workflow(req.config or {}, req.context or {})
