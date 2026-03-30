"""
============================================================
API     : Logistic Compliance Audit API
PURPOSE : FastAPI server that exposes the compliance audit workflow
          as a REST API endpoint.
          - POST /audit  : triggers the full compliance audit pipeline
          - GET  /health : confirms the API is running
============================================================
"""

import uuid
import logging
import os
from logging.handlers import RotatingFileHandler
from contextlib import asynccontextmanager
from typing import List, Optional

# ── LOAD ENVIRONMENT VARIABLES FIRST BEFORE ANYTHING ELSE ──
from dotenv import load_dotenv
load_dotenv(override=True)

# ── FRAMEWORK IMPORTS ──
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# ── SILENCE NOISY AZURE BACKGROUND LOGS ──
# These generate hundreds of lines of ping/telemetry noise that hide real logs.
# Setting them to WARNING means only actual problems will appear.
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("azure.monitor.opentelemetry.exporter").setLevel(logging.WARNING)
logging.getLogger("azure.monitor.opentelemetry").setLevel(logging.WARNING)
logging.getLogger("azure.identity._credentials").setLevel(logging.WARNING)
logging.getLogger("azure.identity._internal").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# ── CONFIGURE MAIN APPLICATION LOGGER ──
_log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs"))
os.makedirs(_log_dir, exist_ok=True)
_log_file = os.path.join(_log_dir, "server.log")

_file_handler = RotatingFileHandler(
    _log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_stream_handler = logging.StreamHandler()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[_stream_handler, _file_handler],
)

logger = logging.getLogger("logistic-compliance-runner")

# ── IMPORTS ──
from backend.src.graph.workflow import app as compliance_graph
from backend.src.api.telemetry import setup_telemetry


# ================================================================
# APPLICATION LIFESPAN
# ================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    ── RUNS ONCE AT STARTUP, INSIDE THE WORKER PROCESS ONLY ──
    This is the correct place to initialize telemetry.
    Module-level calls fire in both the reloader and worker processes,
    causing the 'already instrumented' warning and broken shutdown.
    """
    # Initialize telemetry once in the worker process
    setup_telemetry(app)
    yield


# ================================================================
# DATA MODELS
# ================================================================

class AuditRequest(BaseModel):
    """
    ── INCOMING REQUEST STRUCTURE ──
    Expects a valid video URL string.
    Invalid request returns 422 error.
    """
    video_url: str
    sample_interval_sec: Optional[int] = 2
    max_frames: Optional[int] = 5


class ComplianceIssue(BaseModel):
    """
    ── SINGLE COMPLIANCE VIOLATION ──
    Each violation found in the video is structured this way.
    """
    category: str
    severity: str
    description: str
    recommendation: Optional[str] = None
    rule_citations: Optional[List[dict]] = []


class AuditResponse(BaseModel):
    """
    ── FULL AUDIT RESPONSE STRUCTURE ──
    Returned after the complete pipeline finishes.
    """
    session_id: str
    video_id: str
    status: str
    final_report: str
    compliance_results: List[ComplianceIssue]
    errors: Optional[List[str]] = []
    rules_used: Optional[List[str]] = []
    frames_analyzed: Optional[int] = None


# ================================================================
# FASTAPI APP
# ================================================================

app = FastAPI(
    title="Logistic Compliance Audit API",
    description="API for auditing video content against compliance standards.",
    version="1.0.0",
    lifespan=lifespan,
)


# ================================================================
# MAIN AUDIT ENDPOINT
# ================================================================

@app.post("/audit", response_model=AuditResponse)
async def audit_video(request: AuditRequest):
    """
    ── TRIGGERS THE FULL COMPLIANCE AUDIT PIPELINE ──

    FLOW:
    1. Generate a unique session ID for this request
    2. Pass the video URL into the LangGraph workflow
    3. Workflow downloads, indexes, transcribes and audits the video
    4. Returns structured compliance report with violations and severity
    """
    session_id = str(uuid.uuid4())
    video_id = f"vid_{session_id[:8]}"

    logger.info(f"{'='*50}")
    logger.info(f"NEW AUDIT REQUEST")
    logger.info(f"Session  : {session_id}")
    logger.info(f"Video URL: {request.video_url}")
    logger.info(f"{'='*50}")

    # ── PREPARE INITIAL STATE FOR THE WORKFLOW ──
    initial_inputs = {
        "video_url": request.video_url,
        "video_id": video_id,
        "sample_interval_sec": request.sample_interval_sec,
        "max_frames": request.max_frames,
        "compliance_results": [],
        "errors": [],
    }

    try:
        # ── INVOKE THE LANGGRAPH COMPLIANCE WORKFLOW ──
        final_state = compliance_graph.invoke(initial_inputs)

        # ── BUILD THE RESPONSE FROM THE FINAL WORKFLOW STATE ──
        response = AuditResponse(
            session_id=session_id,
            video_id=final_state.get("video_id", video_id),
            status=final_state.get("final_status", "UNKNOWN"),
            final_report=final_state.get("final_report", "No Report Generated"),
            compliance_results=[
                ComplianceIssue(**issue)
                for issue in final_state.get("compliance_results", [])
            ],
            errors=final_state.get("errors", []),
            rules_used=final_state.get("rules_used", []),
            frames_analyzed=final_state.get("frames_analyzed"),
        )

        logger.info(f"AUDIT COMPLETE | Session: {session_id} | Status: {response.status}")
        return response

    except Exception as e:
        logger.error(f"AUDIT FAILED | Session: {session_id} | Error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Workflow Server Error Failed: {str(e)}"
        )


# ================================================================
# HEALTH CHECK ENDPOINT
# ================================================================

@app.get("/health")
def health_check():
    """
    ── CONFIRMS THE API IS RUNNING ──
    Use this to verify the server is up before sending audit requests.
    """
    logger.info("Health check requested")
    return {
        "status": "healthy",
        "message": "Compliance Audit API is healthy and running."
    }
