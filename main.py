
"""
Main execution entry point for the Compliance QA Pipeline

This file is the 'control room' that starts and manages the entire
compliance audit workflow. Think of it as the master switch that:
1. Sets up the audit request
2. Runs the AI workflow
3. Displays the final compliance report
"""

import uuid
import json
import logging

from dotenv import load_dotenv

from backend.src.graph.workflow import app

load_dotenv(override=True)

# setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("logistic-compliance-runner")


def run_cli_simulation():
    """
    Simulates the video compliance audit request.

    This function orchestrates the entire audit process.
    """

    # generate the session ID
    session_id = str(uuid.uuid4())
    logger.info(f"Starting Audit : {session_id}")

    # define the initial state
    initial_inputs = {
        "video_url": "rtsp://your-camera-stream",
        "video_id": f"vid_{session_id[:8]}",
        "sample_interval_sec": 2,
        "max_frames": 5,
        "compliance_results": [],
        "errors": [],
    }

    print("\n........Initializing workflow.......")
    print(f"Input Payload : {json.dumps(initial_inputs, indent=2)}")

    try:
        final_state = app.invoke(initial_inputs)
        print("\n-------Workflow execution is complete........")

        print("\n Compliance Audit Report ==")
        print(f"Video ID : {final_state.get('video_id')}")
        print(f"Status : {final_state.get('final_status')}")

        print("\n [ VIOLATIONS DETECTED]")
        results = final_state.get("compliance_results", [])
        if results:
            for issue in results:
                print(
                    f"- [{issue.get('severity')}] [{issue.get('category')}] : "
                    f"[{issue.get('description')}]"
                )
        else:
            print("No Violations Detected.......")

        # Display final summary
        print("\n [FINAL SUMMARY]")
        print(final_state.get("final_report"))

    except Exception as e:
        logger.error(f"Workflow Execution Failed : {str(e)}")
        raise


if __name__ == "__main__":
    run_cli_simulation()



'''
The project moved from "Coding to "Product."

Ingestion: (Youtube -> Azure)

Indexing: (Speech-to-Text + OCR)

Retrieval: ( Found the rules about "Class")

Reasoning: (Applied rules to the specific claims in the video)

You are the product manager for a video compliance auditing tool. The tool uses AI to analyze videos for potential compliance issues based on company policies. The main workflow includes:
1. Ingesting videos from sources like YouTube.
2. Indexing video content using Azure Video Indexer (extracting speech-to-text and OCR data).
3. Retrieving relevant compliance rules from a knowledge base.
4. Reasoning over the extracted content and rules to identify potential violations.
'''
