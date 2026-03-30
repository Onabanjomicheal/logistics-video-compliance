import logging
from typing import Dict, Any

from backend.src.graph.state import VideoAuditState
from backend.src.services.frame_sampler import FrameSampler
from backend.src.services.vision_analysis import VisionAnalyzer
from backend.src.services.rag_retriever import RulesRetriever
from backend.src.services.compliance_auditor import ComplianceAuditor

logger = logging.getLogger("Logistic-compliance")
logging.basicConfig(level=logging.INFO)


def observe_scene_node(state: VideoAuditState) -> Dict[str, Any]:
    """
    Samples frames from a live video stream and generates a scene summary
    using Azure AI Vision.
    """
    video_url = state.get("video_url")
    sample_interval = state.get("sample_interval_sec", 2)
    max_frames = state.get("max_frames", 5)

    logger.info(f"----[Node: Observe] Sampling {max_frames} frames every {sample_interval}s")

    sampler = FrameSampler(sample_interval_sec=sample_interval, max_frames=max_frames)
    analyzer = VisionAnalyzer()

    frames = sampler.sample(video_url)
    scene_summaries = []
    ocr_text = []

    for frame_bytes in frames:
        result = analyzer.analyze(frame_bytes)
        if result.get("scene_summary"):
            scene_summaries.append(result["scene_summary"])
            logger.info(f"[Vision] {result['scene_summary']}")
        ocr_text.extend(result.get("ocr_text", []))

    merged_summary = " | ".join(scene_summaries)

    return {
        "frames_analyzed": len(frames),
        "scene_summary": merged_summary,
        "ocr_text": ocr_text,
        "video_metadata": {"source": "live_stream"},
    }


def audit_compliance_node(state: VideoAuditState) -> Dict[str, Any]:
    """
    Runs RAG over compliance rules and audits the current scene.
    """
    scene_summary = state.get("scene_summary", "")
    ocr_text = state.get("ocr_text", [])

    if not scene_summary:
        logger.warning("No scene summary available. Skipping audit.")
        return {
            "final_status": "FAIL",
            "final_report": "Audit skipped because no scene summary was generated.",
        }

    retriever = RulesRetriever()
    auditor = ComplianceAuditor()

    rules_text, sources = retriever.retrieve(scene_summary)
    audit_data = auditor.audit(scene_summary, ocr_text, rules_text)

    return {
        "compliance_results": audit_data.get("compliance_results", []),
        "final_status": audit_data.get("status", "FAIL"),
        "final_report": audit_data.get("final_report", "No report generated."),
        "rules_used": sources,
    }
