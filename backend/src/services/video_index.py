"""
============================================================
SERVICE : Azure Video Indexer Connector
PURPOSE : Handles all communication between the app and Azure Video Indexer
          - Downloads YouTube videos
          - Checks for existing indexed videos (cache)
          - Uploads new videos to Azure
          - Waits for processing to complete
          - Extracts transcript and OCR data
============================================================
"""

import os
import time
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import yt_dlp
from azure.identity import DefaultAzureCredential

logger = logging.getLogger("Video-indexer")


class VideoIndexerServices:
    def __init__(self):
        # ── LOAD AZURE CONFIGURATION FROM ENVIRONMENT VARIABLES ──
        self.account_id = os.getenv("AZURE_VI_ACCOUNT_ID")
        self.location = os.getenv("AZURE_VI_LOCATION")
        self.subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
        self.resource_group = os.getenv("AZURE_RESOURCE_GROUP")
        self.vi_name = os.getenv("AZURE_VI_NAME", "Logisticcomplianceproject")
        # ── INITIALIZE AZURE CREDENTIAL (reads from environment automatically) ──
        self.credential = DefaultAzureCredential()
        # Request session with retries/timeouts
        self._timeout = (
            float(os.getenv("VI_CONNECT_TIMEOUT", "10")),
            float(os.getenv("VI_READ_TIMEOUT", "60")),
        )
        self.session = requests.Session()
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    # ================================================================
    # AUTHENTICATION METHODS
    # ================================================================

    def get_access_token(self):
        """
        ── STEP 1 OF AUTH : Get ARM (Azure Resource Manager) Token ──
        This is the master Azure token needed to talk to any Azure service.
        Without this, nothing else works.
        """
        try:
            token_object = self.credential.get_token("https://management.azure.com/.default")
            return token_object.token
        except Exception as e:
            logger.error(f"Failed to get Azure token: {e}")
            raise

    def get_acess_token(self):
        # ── BACKWARD COMPATIBILITY WRAPPER (typo kept intentionally) ──
        return self.get_access_token()

    def get_account_token(self, arm_access_token):
        """
        ── STEP 2 OF AUTH : Exchange ARM Token for Video Indexer Token ──
        Azure Video Indexer requires its own specific token.
        We use the ARM token to request it from the Video Indexer API.
        This uses the new ARM-based endpoint (NOT the old deprecated Microsoft.Media one).
        """
        url = (
            f"https://management.azure.com/subscriptions/{self.subscription_id}"
            f"/resourceGroups/{self.resource_group}"
            f"/providers/Microsoft.VideoIndexer/accounts/{self.vi_name}"
            f"/generateAccessToken?api-version=2024-01-01"
        )
        headers = {"Authorization": f"Bearer {arm_access_token}"}
        payload = {"permissionType": "Contributor", "scope": "Account"}
        response = self.session.post(url, headers=headers, json=payload, timeout=self._timeout)
        if response.status_code != 200:
            raise Exception(f"Failed to get VI account token: {response.text}")
        return response.json().get("accessToken")

    # ================================================================
    # VIDEO DOWNLOAD
    # ================================================================

    def download_youtube_video(self, url, output_path="temp_video.mp4"):
        """
        ── DOWNLOADS YOUTUBE VIDEO TO LOCAL DISK ──
        Uses yt-dlp library to download the best available format.
        The file is saved temporarily and deleted after upload to Azure.
        """
        logger.info(f"Downloading Youtube video: {url}")
        ydl_opts = {
            "format": "best",
            "outtmpl": output_path,
            "quiet": False,
            "overwrites": False,
            "no_warnings": False,
            # ── TRY ANDROID CLIENT FIRST, FALL BACK TO WEB ──
            "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebkit/537.36"
            },
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                logger.info("Download complete")
                return output_path
        except Exception as e:
            raise Exception(f"Youtube Video Download Failed : {e}")

    # ================================================================
    # DUPLICATE DETECTION (CACHE CHECK)
    # ================================================================

    def find_existing_video(self, video_name):
        """
        ── CHECK IF THIS VIDEO WAS ALREADY INDEXED BEFORE ──
        Before uploading, we search Azure Video Indexer for a video
        with the same stable name (generated from the URL hash).

        WHY THIS EXISTS:
        The same YouTube URL always produces the same video name.
        If we already processed it before, we skip the entire
        download → upload → wait cycle and go straight to the transcript.
        This saves 3-5 minutes on every repeated request.

        Returns the Azure video ID if found and fully processed.
        Returns None if not found or still processing.
        """
        try:
            arm_token = self.get_access_token()
            vi_token = self.get_account_token(arm_token)

            url = f"https://api.videoindexer.ai/{self.location}/Accounts/{self.account_id}/Videos"
            params = {"accessToken": vi_token}
            response = self.session.get(url, params=params, timeout=self._timeout)
            if response.status_code != 200:
                return None

            videos = response.json().get("results", [])
            for video in videos:
                # ── ONLY REUSE IF FULLY PROCESSED (NOT STILL PROCESSING) ──
                if video.get("name") == video_name and video.get("state") == "Processed":
                    logger.info(f"Found existing processed video: {video.get('id')}")
                    return video.get("id")
            return None
        except Exception as e:
            logger.warning(f"Could not check for existing video: {e}")
            return None

    # ================================================================
    # FETCH EXISTING VIDEO INDEX
    # ================================================================

    def get_video_index(self, video_id):
        """
        ── FETCH FULL TRANSCRIPT AND INSIGHTS FOR AN ALREADY PROCESSED VIDEO ──
        Used when we find an existing video in the cache check above.
        Retrieves the complete indexed data without re-processing anything.
        """
        arm_token = self.get_access_token()
        vi_token = self.get_account_token(arm_token)

        url = f"https://api.videoindexer.ai/{self.location}/Accounts/{self.account_id}/Videos/{video_id}/Index"
        params = {"accessToken": vi_token}
        response = self.session.get(url, params=params, timeout=self._timeout)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch video index: {response.text}")
        return response.json()

    # ================================================================
    # VIDEO UPLOAD
    # ================================================================

    def upload_video(self, video_path, video_name):
        """
        ── UPLOADS LOCAL VIDEO FILE TO AZURE VIDEO INDEXER ──
        Only called when no existing indexed version was found.
        Sends the file as a binary stream to the Azure API.
        Returns the Azure-assigned video ID needed for status polling.
        """
        arm_token = self.get_access_token()
        vi_token = self.get_account_token(arm_token)

        api_url = f"https://api.videoindexer.ai/{self.location}/Accounts/{self.account_id}/Videos"
        params = {
            "accessToken": vi_token,
            "name": video_name,
            "privacy": "Private",
            "indexingPreset": "Default",
        }

        logger.info(f"Uploading file {video_path} to Azure.......")
        with open(video_path, "rb") as video_file:
            files = {"file": video_file}
            response = self.session.post(api_url, params=params, files=files, timeout=self._timeout)

        if response.status_code != 200:
            raise Exception(f"Azure upload Failed : {response.text}")
        return response.json()

    # ================================================================
    # PROCESSING MONITOR
    # ================================================================

    def wait_for_processing(self, video_id, timeout_minutes=30):
        """
        ── POLLS AZURE EVERY 30 SECONDS UNTIL VIDEO IS FULLY PROCESSED ──
        Azure Video Indexer processes videos asynchronously on their servers.
        We poll the status endpoint every 30 seconds until it returns "Processed".

        TIMEOUT PROTECTION:
        If Azure takes longer than timeout_minutes (default 10 mins),
        we raise a clean timeout error instead of waiting forever.
        This prevents the API from hanging indefinitely on stuck jobs.

        Possible states:
        - Processing : still working, keep waiting
        - Processed  : done, extract data
        - Failed     : Azure could not process the video
        - Quarantined: video flagged for copyright or content policy
        """
        logger.info(f"Waiting for the video {video_id} to process.....")
        max_wait = timeout_minutes * 60
        elapsed = 0

        while elapsed < max_wait:
            arm_token = self.get_access_token()
            vi_token = self.get_account_token(arm_token)

            url = f"https://api.videoindexer.ai/{self.location}/Accounts/{self.account_id}/Videos/{video_id}/Index"
            params = {"accessToken": vi_token}
            response = self.session.get(url, params=params, timeout=self._timeout)
            if response.status_code != 200:
                raise Exception(f"Failed to fetch video status: {response.text}")
            data = response.json()

            state = data.get("state")
            if state == "Processed":
                return data
            elif state == "Failed":
                raise Exception("Video indexing failed in Azure")
            elif state == "Quarantined":
                raise Exception("Video quarantined (copyright/content policy violation)")

            # ── LOG PROGRESS WITH ELAPSED TIME ──
            logger.info(f"Status {state}......... waiting 30s ({elapsed//60}m {elapsed%60}s elapsed / {timeout_minutes}m max)")
            time.sleep(30)
            elapsed += 30

        raise Exception(f"Video processing timed out after {timeout_minutes} minutes.")

    # ================================================================
    # DATA EXTRACTION
    # ================================================================

    def extract_data(self, vi_json):
        """
        ── PARSES AZURE VIDEO INDEXER JSON INTO OUR APP FORMAT ──
        Azure returns a large JSON with many fields.
        We extract only what we need:
        - transcript : the spoken words from the video
        - ocr_text   : any text visible on screen
        - metadata   : duration and platform info
        """
        # ── EXTRACT SPOKEN TRANSCRIPT ──
        transcript_lines = []
        for v in vi_json.get("videos", []):
            for insight in v.get("insights", {}).get("transcript", []):
                transcript_lines.append(insight.get("text"))

        # ── EXTRACT ON-SCREEN TEXT (OCR) ──
        ocr_lines = []
        for v in vi_json.get("videos", []):
            for insight in v.get("insights", {}).get("ocr", []):
                ocr_lines.append(insight.get("text"))

        return {
            "transcript": " ".join(transcript_lines),
            "ocr_text": ocr_lines,
            "video_metadata": {
                "duration": vi_json.get("summarizedInsights", {}).get("duration"),
                "platform": "youtube",
            },
        }
