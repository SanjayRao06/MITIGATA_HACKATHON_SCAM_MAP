"""Read-only speed check for GET /lookup (target: answers in under 500 ms).

It sends N lookups (default 200) and prints how long they took: median, p95 and slowest.
It only READS: no reports are sent, nothing is reset or deleted, so it is safe to run against
the live server. The numbers it asks about are made up and have never been reported, which is
the common case for a real visitor too.

Run:
    python tools/latency_check.py --base https://mitigata-hackathon-scam-map.onrender.com
    python tools/latency_check.py --base http://localhost:8000 --count 200
"""

import argparse
import http.client
import random
import sys
import time
from pathlib import Path
from urllib.parse import quote, urlparse

# Reuse the HTTP helper from scenarios.py (same folder).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scenarios import LOOKUP_BUDGET_MS  # noqa: E402


def make_lookups(count: int, rng: random.Random) -> list[tuple[str, str]]:
    """In: how many lookups. Out: a mix of (type, value) pairs covering all 4 identifier types.

    Why a mix: the judges' tool looks up phones, UPI IDs, links and SMS senders, so the speed
    check should too. The values are random and unreported, so they come back as "no reports".
    """
    pairs = []
    for i in range(count):
        kind = i % 4
        n = rng.randrange(10 ** 7)
        if kind == 0:
            pairs.append(("phone", f"9{rng.randrange(10 ** 9):09d}"))
        elif kind == 1:
            pairs.append(("upi", f"speedcheck{n}@okaxis"))
        elif kind == 2:
            pairs.append(("url", f"https://speed-check-{n}.example.in/pay"))
        else:
            pairs.append(("sender_id", "SC" + "".join(rng.choice("ABCDEFGH") for _ in range(4))))
    return pairs


def percentile(sorted_ms: list[float], pct: float) -> float:
    """In: sorted times and a percentile such as 0.95. Out: that percentile's time in ms."""
    return sorted_ms[min(len(sorted_ms) - 1, int(len(sorted_ms) * pct))]


def time_requests(base: str, paths: list[str]) -> tuple[list[float], list[float], int]:
    """In: server address and the paths to GET.
    Out: (round-trip ms per request, server's own ms per request, number of non-200 replies).

    The server's own time comes from its Server-Timing header ("app;dur=4.2"), so we can tell
    our code's time apart from the network's.

    Uses ONE kept-open connection, like a test tool that reuses its session, so the TLS handshake
    is paid once and not on every request (it would otherwise dominate the numbers).
    """
    url = urlparse(base.replace("://localhost", "://127.0.0.1", 1))
    cls = http.client.HTTPSConnection if url.scheme == "https" else http.client.HTTPConnection
    conn = cls(url.hostname, url.port, timeout=60)
    times, server_ms, bad = [], [], 0
    for n, path in enumerate(paths, 1):
        if n % 25 == 0 or n == len(paths):
            print(f"  ... {n}/{len(paths)}", flush=True)     # so a slow server doesn't look frozen
        start = time.perf_counter()
        conn.request("GET", path)
        resp = conn.getresponse()
        resp.read()
        times.append((time.perf_counter() - start) * 1000)
        timing = resp.getheader("Server-Timing") or ""
        if "dur=" in timing:
            server_ms.append(float(timing.split("dur=", 1)[1].split(",")[0].split(";")[0]))
        bad += resp.status != 200
    conn.close()
    return times, server_ms, bad


def main(argv=None) -> int:
    """Command-line entry point. Returns 0 if p95 is under the budget, 1 if not, 2 on errors."""
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--base", default="http://localhost:8000", help="server address")
    parser.add_argument("--count", type=int, default=200, help="number of lookups")
    parser.add_argument("--seed", type=int, default=None, help="repeat the same lookups")
    args = parser.parse_args(argv)
    rng = random.Random(args.seed)

    print(f"Timing {args.base} (takes 1-2 minutes) ...", flush=True)

    # 1) Baseline: /health does no database work, so its time is the network + hosting floor.
    base_times, _, _ = time_requests(args.base, ["/health"] * min(args.count, 100))

    # 2) The lookups themselves.
    paths = [f"/lookup?type={t}&value={quote(v)}" for t, v in make_lookups(args.count, rng)]
    times, server_ms, bad = time_requests(args.base, paths)

    # 3) If answers were errors (e.g. licence expired), the timing means nothing.
    if bad:
        print(f"{bad} of {args.count} lookups did not return 200 (licence expired? server down?).")
        return 2

    # 4) Report. "Server adds" = lookup median minus /health median: what our code + database cost.
    ordered, base_ordered = sorted(times), sorted(base_times)
    p95 = percentile(ordered, 0.95)
    extra = percentile(ordered, 0.5) - percentile(base_ordered, 0.5)
    print(f"{args.count} lookups against {args.base} (one kept-open connection)")
    print(f"  /health median (network floor) : {percentile(base_ordered, 0.5):6.0f} ms")
    print(f"  lookup median                  : {percentile(ordered, 0.5):6.0f} ms")
    print(f"  lookup p95                     : {p95:6.0f} ms   (budget {LOOKUP_BUDGET_MS} ms)")
    print(f"  slowest                        : {ordered[-1]:6.0f} ms")
    print(f"  server adds (median - floor)   : {extra:6.0f} ms")
    if server_ms:
        srv = sorted(server_ms)
        print(f"  SERVER'S OWN TIME (header)     : median {percentile(srv, 0.5):.0f} ms, p95 {percentile(srv, 0.95):.0f} ms, max {srv[-1]:.0f} ms")
    ok = p95 < LOOKUP_BUDGET_MS
    print("PASS" if ok else "FAIL (round trip; compare the server's own time above: the rest is network)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
