# Azure Opentelemetry integration

import os
import logging
import ssl
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor

# create a dedicated logger
logger = logging.getLogger("logistic-compliance-telemetry")
logger.setLevel(logging.INFO)

# ── SINGLETON GUARD ──
# Prevents double-initialization when uvicorn --reload spins up
# both a reloader process and a worker process
_telemetry_initialized = False


def setup_telemetry(app=None):
    """
    Initializes Azure Monitor telemetry for the application.
    Tracks: Http requests, errors, exceptions, and metrics.
    Sends this data to azure monitor

    It auto captures every API request
    No need to manually log each endpoint
    """

    global _telemetry_initialized

    # ── SKIP IF ALREADY INITIALIZED ──
    # Uvicorn --reload causes two process imports; this prevents double setup
    if _telemetry_initialized:
        logger.debug("Telemetry already initialized, skipping.")
        return

    # --- FIX FOR 10054 CONNECTION RESET ---
    # This ensures the SSL context is stable for the Live Metrics heartbeat pings
    try:
        ssl._create_default_https_context = ssl._create_unverified_context
    except AttributeError:
        pass

    # get the connection string from environment
    connection_string = os.getenv("APPLICATION_INSIGHTS_CONNECTION_STRING")

    # check if connection string is configured
    if not connection_string:
        logger.warning(
            "No Instrumentation key found. Telemetry is DISABLED.")
        return

    # --- FIX FOR UNKNOWN SERVICE NAME ---
    # Explicitly defining the resource ensures the Application Map is labeled correctly
    service_name = os.getenv("OTEL_SERVICE_NAME", "Logistic-Compliance-API")
    custom_resource = Resource.create({
        SERVICE_NAME: service_name
    })

    # configure azure monitor with the connection string
    try:
        configure_azure_monitor(
            connection_string=connection_string,
            logger_name="logistic-compliance-runner",
            resource=custom_resource  # Replaces 'service_name' for better compatibility
        )

        # Azure Monitor auto-instruments supported libraries (FastAPI, requests,
        # urllib3, httpx) when their instrumentation packages are installed.

        # Manual instrumentation (guarded to avoid double-instrumenting)
        if os.getenv("OTEL_MANUAL_INSTRUMENTATION", "true").lower() in {"1", "true", "yes"}:
            if app is not None:
                FastAPIInstrumentor().instrument_app(app)
            HTTPXClientInstrumentor().instrument()
            RequestsInstrumentor().instrument()
            URLLib3Instrumentor().instrument()

        # ── MARK AS INITIALIZED ──
        _telemetry_initialized = True

        logger.info("Azure Monitor Tracking is ENABLED and CONNECTED.")

    except Exception as e:
        logger.error(f"Failed to Initialize Azure Monitor: {e}")
