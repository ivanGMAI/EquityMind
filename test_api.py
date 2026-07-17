#!/usr/bin/env python
"""Test script for the EquityMind API."""

import asyncio
import sys
import time
from pathlib import Path

# Add src to path
_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import httpx


async def test_api():
    """Test the API with a simple analysis."""
    base_url = "http://localhost:8000"

    async with httpx.AsyncClient(timeout=300) as client:
        # 1. Health check
        print("🔍 Health check...")
        health = await client.get(f"{base_url}/api/health")
        print(f"  Status: {health.status_code}")
        print(f"  Response: {health.json()}\n")

        # 2. Submit analysis
        print("📊 Submitting analysis...")
        analysis_request = {
            "tickers": ["SBER", "GAZP"],
            "period": "3mo",
            "interval": "1d",
            "return_basis": "cumulative",
            "with_ai": False,  # Disable to speed up testing
            "with_backtest": True,
            "source": "moex",
        }
        submit_resp = await client.post(
            f"{base_url}/api/analyze",
            json=analysis_request,
        )
        print(f"  Status: {submit_resp.status_code}")
        submit_data = submit_resp.json()
        print(f"  Response: {submit_data}\n")

        if submit_resp.status_code != 200:
            print("❌ Failed to submit analysis")
            return

        job_id = submit_data["job_id"]
        print(f"✓ Job submitted: {job_id}\n")

        # 3. Poll progress
        print("⏳ Polling progress...")
        max_polls = 180  # 3 minutes max
        poll_count = 0

        while poll_count < max_polls:
            progress_resp = await client.get(f"{base_url}/api/progress/{job_id}")
            progress_data = progress_resp.json()

            status = progress_data["status"]
            progress = progress_data["progress"]
            step = progress_data["current_step"]

            percent = int(progress * 100)
            bar = "█" * (percent // 5) + "░" * (20 - percent // 5)
            print(f"  [{bar}] {percent}% — {step}")

            if status == "done":
                print("\n✅ Analysis complete!\n")
                break
            elif status == "failed":
                print(f"\n❌ Analysis failed: {progress_data.get('error')}\n")
                return

            await asyncio.sleep(2)
            poll_count += 1

        if poll_count >= max_polls:
            print("\n⏱️ Timeout waiting for analysis\n")
            return

        # 4. Get result
        print("📈 Fetching results...")
        result_resp = await client.get(f"{base_url}/api/result/{job_id}")
        result_data = result_resp.json()

        print(f"  Status: {result_resp.status_code}")
        print(f"  Generated at: {result_data.get('generated_at')}")
        print(f"  AI provider: {result_data.get('ai_provider')}")
        print(f"  Assets analyzed: {list(result_data.get('assets', {}).keys())}")

        if "comparison" in result_data and result_data["comparison"]:
            print(f"\n  Ranking:")
            for entry in result_data["comparison"]:
                print(
                    f"    {entry['rank']}. {entry['ticker']} — "
                    f"{entry['return_pct']:+.2f}% return, "
                    f"{entry['volatility_pct']:.1f}% vol"
                )

        print("\n✨ Test completed successfully!")


if __name__ == "__main__":
    try:
        asyncio.run(test_api())
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
