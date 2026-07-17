"""Check the latest finished job's raw result keys via the host-published API."""

import json
import urllib.request

BASE = "http://localhost:8000"

jobs = json.load(urllib.request.urlopen(f"{BASE}/api/jobs"))["jobs"]
print("jobs:", [(j["job_id"][:8], j["status"]) for j in jobs])
done = [j for j in jobs if j["status"] == "done"]
if not done:
    raise SystemExit("no finished jobs")

jid = done[-1]["job_id"]
result = json.load(urllib.request.urlopen(f"{BASE}/api/result/{jid}"))
print("result keys:", sorted(result.keys()))
print("portfolio:", "present" if result.get("portfolio") else repr(result.get("portfolio")))
print("benchmark:", "present" if result.get("benchmark") else repr(result.get("benchmark")))
