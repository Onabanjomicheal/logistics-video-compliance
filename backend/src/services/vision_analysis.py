import os
import requests


class VisionAnalyzer:
    def __init__(self):
        self.endpoint = os.getenv("AZURE_VISION_ENDPOINT")
        self.key = os.getenv("AZURE_VISION_KEY")
        self.api_version = os.getenv("AZURE_VISION_API_VERSION", "2024-02-01")

        if not self.endpoint or not self.key:
            raise RuntimeError("Azure Vision endpoint/key not configured.")

    def analyze(self, image_bytes):
        url = f"{self.endpoint.rstrip('/')}/computervision/imageanalysis:analyze"
        params = {
            "api-version": self.api_version,
            "features": "caption,read,objects,tags",
        }
        headers = {
            "Ocp-Apim-Subscription-Key": self.key,
            "Content-Type": "application/octet-stream",
        }
        resp = requests.post(url, params=params, headers=headers, data=image_bytes, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"Vision analysis failed: {resp.status_code} {resp.text}")

        data = resp.json()
        caption = (data.get("captionResult") or {}).get("text", "")
        tags = [t.get("name") for t in data.get("tagsResult", {}).get("values", []) if t.get("name")]
        objects = [o.get("tags", [{}])[0].get("name") for o in data.get("objectsResult", {}).get("values", [])]

        ocr_lines = []
        read = data.get("readResult", {})
        for block in read.get("blocks", []):
            for line in block.get("lines", []):
                ocr_lines.append(line.get("text", ""))

        scene_summary = " | ".join(
            [caption] + ([", ".join(tags)] if tags else []) + ([", ".join(objects)] if objects else [])
        ).strip(" |")

        return {
            "caption": caption,
            "tags": tags,
            "objects": objects,
            "ocr_text": ocr_lines,
            "scene_summary": scene_summary,
        }
