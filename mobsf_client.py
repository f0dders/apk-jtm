import requests
import time
from pathlib import Path


class MobSFClient:
    def __init__(self, url: str, api_key: str):
        self.url = url.rstrip("/")
        self.headers = {"Authorization": api_key}

    def upload(self, apk_path: str) -> dict:
        path = Path(apk_path)
        with open(path, "rb") as f:
            response = requests.post(
                f"{self.url}/api/v1/upload",
                headers=self.headers,
                files={"file": (path.name, f, "application/octet-stream")},
            )
        response.raise_for_status()
        return response.json()

    def scan(self, file_name: str, hash: str) -> dict:
        response = requests.post(
            f"{self.url}/api/v1/scan",
            headers=self.headers,
            data={"scan_type": "apk", "file_name": file_name, "hash": hash},
        )
        response.raise_for_status()
        return response.json()

    def get_report(self, hash: str) -> dict:
        response = requests.post(
            f"{self.url}/api/v1/report_json",
            headers=self.headers,
            data={"hash": hash},
        )
        response.raise_for_status()
        return response.json()

    def get_scorecard(self, hash: str) -> dict:
        response = requests.post(
            f"{self.url}/api/v1/scorecard",
            headers=self.headers,
            data={"hash": hash},
        )
        response.raise_for_status()
        return response.json()

    def _merge_scorecard(self, report: dict, hash: str) -> dict:
        """Fetch scorecard and merge security_score + average_cvss into the report."""
        try:
            scorecard = self.get_scorecard(hash)
            report["security_score"] = scorecard.get("security_score", report.get("security_score", "N/A"))
            report["average_cvss"] = scorecard.get("average_cvss", report.get("average_cvss", "N/A"))
        except Exception:
            pass
        return report

    def upload_and_scan(self, apk_path: str, poll_interval: int = 3) -> dict:
        upload_result = self.upload(apk_path)
        file_name = upload_result["file_name"]
        hash = upload_result["hash"]

        # Check if MobSF already has results for this APK (same hash = same file)
        try:
            report = self.get_report(hash)
            if report.get("app_name"):
                report["_cached"] = True
                return self._merge_scorecard(report, hash)
        except requests.HTTPError:
            pass

        # No cached result — run the full scan
        self.scan(file_name, hash)

        for _ in range(60):
            try:
                report = self.get_report(hash)
                if report.get("app_name"):
                    return self._merge_scorecard(report, hash)
            except requests.HTTPError:
                pass
            time.sleep(poll_interval)

        raise TimeoutError("MobSF scan did not complete within 3 minutes.")
