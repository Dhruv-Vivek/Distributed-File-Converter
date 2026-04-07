"""
Performance Graph Generator
=============================
Reads performance_results.csv and generates detailed graphs.

Usage:
  python utils/plot_performance.py

Requirements:
  pip install matplotlib

Outputs:
  performance_graph.png  <- saved in CN_PROJECT root
"""

import csv
import os
import sys

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.gridspec import GridSpec
except ImportError:
    print("matplotlib not installed. Run: pip install matplotlib")
    sys.exit(1)

# ── Load CSV ──────────────────────────────────────────────────────────────────
CSV_PATH  = os.path.join(os.path.dirname(__file__), "../performance_results.csv")
SAVE_PATH = os.path.join(os.path.dirname(__file__), "../performance_graph.png")

if not os.path.exists(CSV_PATH):
    print(f"[ERROR] performance_results.csv not found.")
    print(f"  Run 'python utils/performance_analysis.py' first to generate data.")
    sys.exit(1)

rows = []
with open(CSV_PATH, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row.get("status") == "success":
            rows.append({
                "label":      row["label"],
                "input_kb":   float(row["input_kb"]),
                "output_kb":  float(row.get("output_kb", 0)),
                "upload_ms":  float(row.get("upload_ms", 0)),
                "server_ms":  float(row["server_ms"]),
                "total_ms":   float(row["total_ms"]),
            })

if not rows:
    print("[ERROR] No successful results found in CSV.")
    sys.exit(1)

# ── Separate TXT->PDF and CSV->JSON rows ─────────────────────────────────────
txt_rows = [r for r in rows if r["label"].startswith("txt")]
csv_rows = [r for r in rows if r["label"].startswith("csv")]
all_rows = sorted(rows, key=lambda r: r["input_kb"])

# ── Plot Setup ────────────────────────────────────────────────────────────────
plt.style.use("seaborn-v0_8-whitegrid")
fig = plt.figure(figsize=(16, 10))
fig.patch.set_facecolor("#F8FAFC")
gs = GridSpec(2, 2, figure=fig, hspace=0.4, wspace=0.35)

BLUE   = "#2563EB"
RED    = "#DC2626"
GREEN  = "#16A34A"
ORANGE = "#EA580C"
PURPLE = "#7C3AED"

# ── Graph 1: Server Time vs File Size (all data) ──────────────────────────────
ax1 = fig.add_subplot(gs[0, 0])
sizes  = [r["input_kb"] for r in all_rows]
s_time = [r["server_ms"] for r in all_rows]
t_time = [r["total_ms"] for r in all_rows]

ax1.plot(sizes, s_time, "o-", color=BLUE,  linewidth=2, markersize=7, label="Server conversion (ms)")
ax1.plot(sizes, t_time, "s--", color=RED,  linewidth=2, markersize=7, label="Total round-trip (ms)")
ax1.fill_between(sizes, s_time, t_time, alpha=0.08, color=RED)
ax1.fill_between(sizes, 0, s_time, alpha=0.08, color=BLUE)
ax1.set_title("Conversion Time vs File Size", fontsize=13, fontweight="bold", pad=10)
ax1.set_xlabel("Input File Size (KB)")
ax1.set_ylabel("Time (ms)")
ax1.legend(fontsize=9)
ax1.set_facecolor("#FFFFFF")

# Annotate max point
max_row = max(all_rows, key=lambda r: r["total_ms"])
ax1.annotate(
    f"  {max_row['total_ms']:.0f} ms",
    xy=(max_row["input_kb"], max_row["total_ms"]),
    fontsize=8, color=RED
)

# ── Graph 2: Upload vs Server vs Total (stacked bar) ─────────────────────────
ax2 = fig.add_subplot(gs[0, 1])
labels     = [r["label"].replace("txt->pdf_", "").replace("csv->json_", "") for r in all_rows]
upload_ms  = [r["upload_ms"] for r in all_rows]
server_ms  = [r["server_ms"] for r in all_rows]
overhead   = [max(0, r["total_ms"] - r["server_ms"] - r["upload_ms"]) for r in all_rows]

x = range(len(labels))
b1 = ax2.bar(x, upload_ms,  color=GREEN,  label="Upload time",    alpha=0.85)
b2 = ax2.bar(x, server_ms,  bottom=upload_ms, color=BLUE, label="Server conv.", alpha=0.85)
b3 = ax2.bar(x, overhead,
             bottom=[u+s for u,s in zip(upload_ms, server_ms)],
             color=ORANGE, label="Network overhead", alpha=0.85)

ax2.set_xticks(x)
ax2.set_xticklabels(labels, rotation=35, ha="right", fontsize=8)
ax2.set_title("Time Breakdown per Job", fontsize=13, fontweight="bold", pad=10)
ax2.set_ylabel("Time (ms)")
ax2.legend(fontsize=9)
ax2.set_facecolor("#FFFFFF")

# ── Graph 3: TXT->PDF scaling ─────────────────────────────────────────────────
ax3 = fig.add_subplot(gs[1, 0])
if txt_rows:
    txt_sorted = sorted(txt_rows, key=lambda r: r["input_kb"])
    tx = [r["input_kb"] for r in txt_sorted]
    ty = [r["server_ms"] for r in txt_sorted]
    ax3.plot(tx, ty, "o-", color=PURPLE, linewidth=2.5, markersize=8)
    ax3.fill_between(tx, ty, alpha=0.1, color=PURPLE)
    for r in txt_sorted:
        ax3.annotate(
            f"{r['server_ms']:.1f}ms",
            xy=(r["input_kb"], r["server_ms"]),
            xytext=(0, 8), textcoords="offset points",
            ha="center", fontsize=8, color=PURPLE
        )
    ax3.set_title("TXT -> PDF: Server Time vs Size", fontsize=13, fontweight="bold", pad=10)
    ax3.set_xlabel("File Size (KB)")
    ax3.set_ylabel("Server Conversion Time (ms)")
    ax3.set_facecolor("#FFFFFF")
else:
    ax3.text(0.5, 0.5, "No TXT->PDF data", ha="center", va="center", transform=ax3.transAxes)
    ax3.set_title("TXT -> PDF: Server Time vs Size", fontsize=13, fontweight="bold")

# ── Graph 4: Throughput (KB/s) ────────────────────────────────────────────────
ax4 = fig.add_subplot(gs[1, 1])
throughput = []
for r in all_rows:
    if r["upload_ms"] > 0:
        throughput.append(r["input_kb"] / (r["upload_ms"] / 1000))
    else:
        throughput.append(0)

colors_bar = [BLUE if t > 0 else "#CBD5E1" for t in throughput]
bars = ax4.bar(range(len(all_rows)), throughput, color=colors_bar, alpha=0.85, edgecolor="white")
ax4.set_xticks(range(len(all_rows)))
ax4.set_xticklabels(
    [r["label"].replace("txt->pdf_","").replace("csv->json_","") for r in all_rows],
    rotation=35, ha="right", fontsize=8
)
ax4.set_title("Upload Throughput per Job", fontsize=13, fontweight="bold", pad=10)
ax4.set_ylabel("Throughput (KB/s)")
ax4.set_facecolor("#FFFFFF")

# Add value labels on bars
for bar, val in zip(bars, throughput):
    if val > 0:
        ax4.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(throughput) * 0.01,
            f"{val:.0f}",
            ha="center", va="bottom", fontsize=7.5, color="#1E40AF"
        )

# ── Main Title ────────────────────────────────────────────────────────────────
fig.suptitle(
    "Distributed File Conversion Service — Performance Analysis",
    fontsize=15, fontweight="bold", color="#1E293B", y=0.98
)

# ── Stats Summary Box ─────────────────────────────────────────────────────────
avg_server = sum(r["server_ms"] for r in rows) / len(rows)
avg_total  = sum(r["total_ms"]  for r in rows) / len(rows)
max_size   = max(r["input_kb"]  for r in rows)
summary = (
    f"Total jobs: {len(rows)}   |   "
    f"Avg server time: {avg_server:.1f} ms   |   "
    f"Avg total time: {avg_total:.1f} ms   |   "
    f"Max file tested: {max_size:.0f} KB"
)
fig.text(0.5, 0.01, summary, ha="center", fontsize=9,
         color="#64748B", style="italic")

# ── Save ──────────────────────────────────────────────────────────────────────
plt.savefig(SAVE_PATH, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
print(f"\n[OK] Graph saved to: {SAVE_PATH}")
print(f"     Open it in File Explorer to view.\n")