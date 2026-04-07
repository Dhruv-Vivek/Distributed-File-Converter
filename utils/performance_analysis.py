"""
Performance Analysis Script
============================
Sends multiple files of increasing size to the server concurrently
and plots conversion time vs. file size.

Usage:
  python performance_analysis.py

Outputs:
  - Console table
  - performance_results.csv
  - performance_plot.png  (if matplotlib available)
"""

import os
import sys
import time
import csv
import threading
import random
import string
import json

# Add parent dir so we can import client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../client"))
from client import convert_file

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "../perf_test_files")
RESULTS    = []
LOCK       = threading.Lock()
os.makedirs(OUTPUT_DIR, exist_ok=True)


def generate_txt_file(size_kb):
    """Generate a text file of approximately `size_kb` kilobytes."""
    path = os.path.join(OUTPUT_DIR, f"test_{size_kb}kb.txt")
    target = size_kb * 1024
    with open(path, "w") as f:
        written = 0
        while written < target:
            line = ''.join(random.choices(string.ascii_letters + " ", k=79)) + "\n"
            f.write(line)
            written += len(line)
    return path


def generate_csv_file(rows):
    """Generate a CSV file with `rows` data rows."""
    size_kb = rows // 10  # Approximate
    path = os.path.join(OUTPUT_DIR, f"test_{rows}rows.csv")
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "name", "score", "timestamp", "value"])
        for i in range(rows):
            writer.writerow([
                i,
                ''.join(random.choices(string.ascii_letters, k=8)),
                round(random.uniform(0, 100), 2),
                f"2024-01-{(i%28)+1:02d}",
                random.randint(100, 9999),
            ])
    return path


def run_test(label, file_path, output_ext, results_list):
    """Run a single conversion test and record results."""
    print(f"\n  → Testing: {label}")
    try:
        result = convert_file(file_path, output_ext, verbose=False)
        if result and result["status"] == "success":
            entry = {
                "label":        label,
                "input_kb":     round(result["input_bytes"] / 1024, 2),
                "output_kb":    round(result["output_bytes"] / 1024, 2),
                "upload_ms":    result["upload_ms"],
                "server_ms":    result["server_ms"],
                "total_ms":     result["total_ms"],
                "status":       "success",
            }
            print(f"     ✓ {label}: {result['total_ms']:.0f} ms total (server: {result['server_ms']:.0f} ms)")
        else:
            entry = {"label": label, "status": "error", "error": str(result)}
            print(f"     ✗ {label}: FAILED")
    except Exception as e:
        entry = {"label": label, "status": "error", "error": str(e)}
        print(f"     ✗ {label}: Exception - {e}")

    with LOCK:
        results_list.append(entry)


def run_concurrent_test(file_path, output_ext, n_clients=5):
    """Send n_clients requests simultaneously and measure overall time."""
    print(f"\n  → Concurrent test: {n_clients} clients simultaneously")
    threads = []
    results = []
    t_start = time.time()

    for i in range(n_clients):
        t = threading.Thread(
            target=run_test,
            args=(f"concurrent_{i+1}", file_path, output_ext, results)
        )
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    elapsed = time.time() - t_start
    successes = sum(1 for r in results if r.get("status") == "success")
    avg_ms = sum(r.get("total_ms", 0) for r in results if r.get("status") == "success")
    avg_ms = avg_ms / successes if successes else 0

    print(f"\n  ── Concurrent Results ({n_clients} clients) ──")
    print(f"     Successes   : {successes}/{n_clients}")
    print(f"     Wall time   : {elapsed*1000:.0f} ms")
    print(f"     Avg per job : {avg_ms:.0f} ms")
    return results


def print_table(results):
    if not results:
        return
    print(f"\n{'='*70}")
    print(f"  {'Label':<20} {'Input KB':>10} {'Server ms':>10} {'Total ms':>10} {'Status':<10}")
    print(f"  {'-'*20} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")
    for r in results:
        if r["status"] == "success":
            print(f"  {r['label']:<20} {r['input_kb']:>10.1f} {r['server_ms']:>10.0f} {r['total_ms']:>10.0f} {'✓'}")
        else:
            print(f"  {r['label']:<20} {'—':>10} {'—':>10} {'—':>10} ✗ error")
    print(f"{'='*70}")


def save_csv(results, path):
    if not results:
        return
    keys = ["label", "input_kb", "output_kb", "upload_ms", "server_ms", "total_ms", "status"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    print(f"\n  Results saved: {path}")


def try_plot(results, path):
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches

        ok = [r for r in results if r.get("status") == "success"]
        if not ok:
            return

        sizes  = [r["input_kb"] for r in ok]
        s_times = [r["server_ms"] for r in ok]
        t_times = [r["total_ms"] for r in ok]

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(sizes, s_times, "o-", color="#2563EB", label="Server conversion time (ms)")
        ax.plot(sizes, t_times, "s--", color="#DC2626", label="Total round-trip time (ms)")
        ax.fill_between(sizes, s_times, t_times, alpha=0.1, color="#DC2626")

        ax.set_xlabel("Input File Size (KB)", fontsize=12)
        ax.set_ylabel("Time (ms)", fontsize=12)
        ax.set_title("Distributed File Conversion: Performance vs File Size", fontsize=14, fontweight="bold")
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.set_facecolor("#F9FAFB")
        fig.tight_layout()
        plt.savefig(path, dpi=150)
        print(f"  Plot saved: {path}")
    except ImportError:
        print("  (matplotlib not installed — skipping plot)")


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "="*55)
    print("  Performance Analysis - Distributed File Conversion")
    print("="*55)

    all_results = []

    # ── Test 1: TXT→PDF at increasing sizes ──────────────────────────────────
    print("\n[1] TXT → PDF: Scaling file size")
    sizes_kb = [1, 5, 10, 50, 100, 250]
    for sz in sizes_kb:
        fp = generate_txt_file(sz)
        run_test(f"txt→pdf_{sz}kb", fp, ".pdf", all_results)

    # ── Test 2: CSV→JSON at increasing row counts ─────────────────────────────
    print("\n[2] CSV → JSON: Scaling row count")
    row_counts = [50, 200, 500, 1000]
    for rows in row_counts:
        fp = generate_csv_file(rows)
        run_test(f"csv→json_{rows}rows", fp, ".json", all_results)

    # ── Test 3: Concurrent clients ───────────────────────────────────────────
    print("\n[3] Concurrent Clients (5 simultaneous)")
    base_file = generate_txt_file(20)
    concurrent_results = run_concurrent_test(base_file, ".pdf", n_clients=5)
    # Don't add to main table (separate analysis)

    # ── Summary ──────────────────────────────────────────────────────────────
    print_table(all_results)

    out_dir = os.path.join(os.path.dirname(__file__), "..")
    save_csv(all_results, os.path.join(out_dir, "performance_results.csv"))
    try_plot(all_results, os.path.join(out_dir, "performance_plot.png"))

    print("\n  Analysis complete!\n")
