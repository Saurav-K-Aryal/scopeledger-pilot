#!/usr/bin/env python3
"""Plot the included actual-data snapshot. No Java, scanner, or model is run."""
from pathlib import Path
import argparse
import hashlib
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

HERE = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-source-root", type=Path,
                        help="Optional original workspace/repository root for SHA verification")
    parser.add_argument("--verify-publication-root", type=Path,
                        help="Verify published files through the path-normalization provenance manifest")
    args = parser.parse_args()
    data = json.loads((HERE / "figure_data.json").read_text())
    if args.verify_source_root:
        for source in data["provenance"]:
            actual = hashlib.sha256((args.verify_source_root / source["path"]).read_bytes()).hexdigest()
            if actual != source["sha256"]:
                raise ValueError(f"SHA-256 mismatch: {source['path']}")
    if args.verify_publication_root:
        root = args.verify_publication_root
        provenance = json.loads((root / "PUBLICATION_PROVENANCE.json").read_text())
        mapping = {row["source"]: row for row in provenance["files"]}
        for source in data["provenance"]:
            row = mapping[source["path"]]
            if row["source_sha256"] != source["sha256"]:
                raise ValueError(f"Original source identity mismatch: {source['path']}")
            actual = hashlib.sha256((root / row["published"]).read_bytes()).hexdigest()
            if actual != row["published_sha256"]:
                raise ValueError(f"Published file mismatch: {row['published']}")
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "savefig.dpi": 220, "figure.dpi": 120})
    out = HERE / "figures"
    out.mkdir(exist_ok=True)
    names = ["DirectResolve.java", "FileJoin.java", "CheckedNormalize.java",
             "DotDotFilter.java", "ConstantFile.java", "StringPrefix.java"]
    probes = ["legitimate", "parent_escape", "absolute_escape", "prefix_sibling_escape"]
    keyed = {(r["file"], r["probe"]): r for r in data["probes"]}
    matrix = [[int(keyed[(f, p)]["disclosure"]) for p in probes] for f in names]
    fig, ax = plt.subplots(figsize=(7.8, 2.9), constrained_layout=True)
    ax.imshow(matrix, cmap=ListedColormap(["#eef1f3", "#b55142"]), vmin=0, vmax=1,
              aspect="auto")
    ax.set_xticks(range(4), ["Inside", "Parent escape", "Absolute escape", "Sibling prefix"])
    ax.set_yticks(range(6), [f.replace(".java", "") for f in names])
    for i, f in enumerate(names):
        for j, p in enumerate(probes):
            r = keyed[(f, p)]
            label = "DISCLOSE" if r["disclosure"] else ("X" if r["returncode"] else "-")
            ax.text(j, i, label, ha="center", va="center", fontsize=8,
                    color="white" if r["disclosure"] else "#33434a")
    ax.set_title("24 actual Java executions; four files disclose in at least one probe", fontsize=10)
    ax.spines[["left", "bottom"]].set_visible(False)
    ax.tick_params(length=0)
    fig.savefig(out / "probe_outcomes.png")
    plt.close(fig)

    conditions = ["clean_current", "stale_previous_revision", "partial_current", "omitted_rule_pack"]
    labels = ["Clean current", "Stale previous", "Partial current", "Omitted rule\n(simulated)"]
    arms = ["unqualified_report_consumer", "scope_qualified_consumer"]
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 2.8), constrained_layout=True)
    for ax, key, title, ymax in zip(axes,
                                  ["false_clearances", "insufficient_evidence"],
                                  ["(a) False clearances (4 observed-disclosing files)",
                                   "(b) Insufficient evidence (6 target files)"], [4.8, 7.2]):
        for offset, arm, color, label in zip([-.18, .18], arms,
                                            ["#b55142", "#237a67"],
                                            ["Unqualified", "Scope qualified"]):
            values = [data["metrics"]["conditions"][c][arm][key] for c in conditions]
            bars = ax.bar([i+offset for i in range(4)], values, width=.36,
                          color=color, label=label)
            ax.bar_label(bars, padding=2, fontsize=8)
        ax.set_xticks(range(4), labels, fontsize=8)
        ax.set_ylim(0, ymax)
        ax.set_yticks(range(int(ymax)+1))
        ax.set_title(title, fontsize=9)
        ax.set_axisbelow(True)
        ax.grid(axis="y", alpha=.16)
    axes[0].set_ylabel("File count")
    axes[1].legend(frameon=False, fontsize=8, ncol=2, loc="upper left")
    fig.savefig(out / "scope_outcomes.png")
    plt.close(fig)
    print("Generated figures/probe_outcomes.png and figures/scope_outcomes.png")

if __name__ == "__main__":
    main()
