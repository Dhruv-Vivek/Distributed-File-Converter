"""
Real Conversion History Graph
==============================
Reads the actual performance_log.csv (written by the server every time
YOU convert a file) and shows graphs of YOUR real conversions.

Usage:
  python utils/plot_my_conversions.py

Requirements:
  pip install matplotlib

Output:
  my_conversions_graph.png  in CN_PROJECT root
"""

import csv
import os
import sys
from datetime import datetime
from collections import defaultdict

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.gridspec import GridSpec
    import matplotlib.dates as mdates
except ImportError:
    print("matplotlib not installed. Run: pip install matplotlib")
    sys.exit(1)

# ── Load real log ─────────────────────────────────────────────────────────────
LOG_PATH  = os.path.join(os.path.dirname(__file__), "../performance_log.csv")
SAVE_PATH = os.path.join(os.path.dirname(__file__), "../my_conversions_graph.png")

if not os.path.exists(LOG_PATH):
    print("[ERROR] performance_log.csv not found.")
    print("  Convert some files first using: python client/client.py <file> <ext>")
    sys.exit(1)

rows = []
with open(LOG_PATH, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            rows.append({
                "timestamp":  datetime.fromisoformat(row["timestamp"]),
                "job_id":     row["job_id"],
                "filename":   row["filename"],
                "output_ext": row["output_ext"],
                "input_kb":   round(int(row["input_size_bytes"]) / 1024, 2),
                "elapsed_ms": round(float(row["elapsed_sec"]) * 1000, 2),
                "status":     row["status"],
            })
        except Exception:
            continue

if not rows:
    print("[ERROR] No data found in performance_log.csv.")
    sys.exit(1)

success = [r for r in rows if r["status"] == "success"]
errors  = [r for r in rows if r["status"] != "success"]

print(f"\n  Found {len(rows)} total conversions ({len(success)} success, {len(errors)} errors)\n")

# ── Colors ────────────────────────────────────────────────────────────────────
EXT_COLORS = {
    ".pdf":  "#2563EB",
    ".json": "#16A34A",
    ".csv":  "#EA580C",
    ".png":  "#7C3AED",
}
def ext_color(ext):
    return EXT_COLORS.get(ext, "#64748B")

# ── Plot ──────────────────────────────────────────────────────────────────────
plt.style.use("seaborn-v0_8-whitegrid")
fig = plt.figure(figsize=(16, 11))
fig.patch.set_facecolor("#F8FAFC")
gs = GridSpec(2, 2, figure=fig, hspace=0.45, wspace=0.35)

# ── Graph 1: Every conversion — time vs file size (scatter) ──────────────────
ax1 = fig.add_subplot(gs[0, 0])

# Group by output format
by_ext = defaultdict(list)
for r in success:
    by_ext[r["output_ext"]].append(r)

for ext, group in by_ext.items():
    xs = [r["input_kb"]   for r in group]
    ys = [r["elapsed_ms"] for r in group]
    ax1.scatter(xs, ys, label=f"-> {ext}", color=ext_color(ext),
                s=80, alpha=0.85, edgecolors="white", linewidth=0.8)
    # Connect dots with a line if more than 1 point
    if len(group) > 1:
        sorted_g = sorted(group, key=lambda r: r["input_kb"])
        ax1.plot(
            [r["input_kb"] for r in sorted_g],
            [r["elapsed_ms"] for r in sorted_g],
            color=ext_color(ext), alpha=0.3, linewidth=1.2
        )

# Mark errors in red
if errors:
    ax1.scatter(
        [r["input_kb"] for r in errors],
        [0] * len(errors),
        marker="x", color="red", s=100, label="Error", zorder=5
    )

ax1.set_title("Your Conversions: Time vs File Size", fontsize=13, fontweight="bold", pad=10)
ax1.set_xlabel("Input File Size (KB)")
ax1.set_ylabel("Server Conversion Time (ms)")
ax1.legend(fontsize=9)
ax1.set_facecolor("#FFFFFF")

# ── Graph 2: Conversion timeline (when you ran each job) ─────────────────────
ax2 = fig.add_subplot(gs[0, 1])

for r in rows:
    color = ext_color(r["output_ext"]) if r["status"] == "success" else "red"
    marker = "o" if r["status"] == "success" else "x"
    ax2.scatter(r["timestamp"], r["elapsed_ms"],
                color=color, marker=marker, s=70, alpha=0.85, edgecolors="white")

# Add extension legend
legend_patches = [
    mpatches.Patch(color=c, label=f"-> {e}") for e, c in EXT_COLORS.items()
    if any(r["output_ext"] == e for r in rows)
]
if errors:
    legend_patches.append(mpatches.Patch(color="red", label="Error"))
ax2.legend(handles=legend_patches, fontsize=9)

ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
plt.setp(ax2.xaxis.get_majorticklabels(), rotation=30, ha="right", fontsize=8)
ax2.set_title("Conversion Timeline", fontsize=13, fontweight="bold", pad=10)
ax2.set_xlabel("Time of conversion")
ax2.set_ylabel("Server Conversion Time (ms)")
ax2.set_facecolor("#FFFFFF")

# ── Graph 3: Count of conversions by type (bar chart) ────────────────────────
ax3 = fig.add_subplot(gs[1, 0])

type_counts = defaultdict(lambda: {"success": 0, "error": 0})
for r in rows:
    label = f"{os.path.splitext(r['filename'])[1] or 'unknown'} -> {r['output_ext']}"
    if r["status"] == "success":
        type_counts[label]["success"] += 1
    else:
        type_counts[label]["error"] += 1

type_labels  = list(type_counts.keys())
success_vals = [type_counts[l]["success"] for l in type_labels]
error_vals   = [type_counts[l]["error"]   for l in type_labels]
x = range(len(type_labels))

bars1 = ax3.bar(x, success_vals, color="#16A34A", alpha=0.85, label="Success")
bars2 = ax3.bar(x, error_vals, bottom=success_vals, color="#DC2626", alpha=0.85, label="Error")

ax3.set_xticks(x)
ax3.set_xticklabels(type_labels, rotation=30, ha="right", fontsize=9)
ax3.set_title("Conversions by Type", fontsize=13, fontweight="bold", pad=10)
ax3.set_ylabel("Number of Jobs")
ax3.legend(fontsize=9)
ax3.set_facecolor("#FFFFFF")

# Add count labels
for bar in bars1:
    h = bar.get_height()
    if h > 0:
        ax3.text(bar.get_x() + bar.get_width()/2, h/2,
                 str(int(h)), ha="center", va="center",
                 fontsize=10, fontweight="bold", color="white")

# ── Graph 4: File size distribution of what YOU converted ────────────────────
ax4 = fig.add_subplot(gs[1, 1])

if success:
    sizes = [r["input_kb"] for r in success]
    colors_list = [ext_color(r["output_ext"]) for r in success]
    job_labels  = [
        f"{os.path.splitext(r['filename'])[1]} -> {r['output_ext']}\n{r['input_kb']} KB"
        for r in success
    ]

    bars = ax4.barh(range(len(success)), sizes, color=colors_list, alpha=0.85, edgecolor="white")

    ax4.set_yticks(range(len(success)))
    ax4.set_yticklabels(
        [f"{r['output_ext']}  {r['elapsed_ms']:.0f}ms" for r in success],
        fontsize=8
    )
    ax4.set_xlabel("Input File Size (KB)")
    ax4.set_title("Your Files: Size & Conversion Time", fontsize=13, fontweight="bold", pad=10)
    ax4.set_facecolor("#FFFFFF")

    # Add KB labels on bars
    for bar, r in zip(bars, success):
        ax4.text(bar.get_width() + max(sizes)*0.01, bar.get_y() + bar.get_height()/2,
                 f"{r['input_kb']} KB", va="center", fontsize=8, color="#374151")

# ── Main title ────────────────────────────────────────────────────────────────
fig.suptitle(
    "Distributed File Conversion Service — My Conversion History",
    fontsize=15, fontweight="bold", color="#1E293B", y=0.98
)

# ── Summary footer ────────────────────────────────────────────────────────────
if success:
    avg_ms   = sum(r["elapsed_ms"] for r in success) / len(success)
    total_kb = sum(r["input_kb"]   for r in success)
    first    = min(r["timestamp"]  for r in rows)
    last     = max(r["timestamp"]  for r in rows)
    summary  = (
        f"Total conversions: {len(rows)}   |   "
        f"Successful: {len(success)}   |   "
        f"Avg conversion time: {avg_ms:.1f} ms   |   "
        f"Total data processed: {total_kb:.1f} KB   |   "
        f"Period: {first.strftime('%H:%M:%S')} - {last.strftime('%H:%M:%S')}"
    )
    fig.text(0.5, 0.01, summary, ha="center", fontsize=9,
             color="#64748B", style="italic")

# ── Save ──────────────────────────────────────────────────────────────────────
plt.savefig(SAVE_PATH, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
print(f"  [OK] Graph saved: {SAVE_PATH}")
print(f"       Open CN_PROJECT/my_conversions_graph.png to view it.\n")