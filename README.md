# ScopeLedger: Java and Semgrep provenance pilot

This repository reports a small Semgrep and Java pilot of how deterministic consumers qualify static-analysis evidence by revision, files, source hashes, and rule identity. Repository: https://github.com/Saurav-K-Aryal/scopeledger-pilot.

The experiment evaluates how a deterministic consumer uses static-analysis evidence. It compiles six authored Java path-reading fixtures, executes four local probes per fixture, and uses Semgrep 1.183.0 with one authored taint rule. It makes no model calls. Code, experiment execution, analysis, and manuscript preparation used Codex assistance under the author's direction.

## Run the experiment

Install Python with a native interpreter supported by Semgrep, a Java JDK providing both `java` and `javac`, and Git. The original run used Python 3.14.2 on macOS arm64. Semgrep 1.183.0 supports Apple Silicon; it does not provide native Intel Mac binaries. No model weights, cloud account, or GPU are required.

From the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
java -version
javac -version
git --version
python run_experiment.py --out results/newrun --profile pilot --seed 2026
```

`run_experiment.py` selects real Semgrep explicitly. It preserves the original experiment module and records the resulting metrics and source hashes. Choose a new empty `--out` directory for each run; nonempty output directories are rejected. The toy lexical scanner available inside the original module is not used by this wrapper or by any paper result.

The output contains `result.json`, `analysis_reports.json`, the authored rule, 24 Java probe rows, 48 consumer-decision rows, and the generated local Java/Git fixture. Actual timings, Git revisions, and local paths can differ. Compare the observed effects and consumer counts rather than byte-identical timestamps.

## Observed results

Four of the six fixtures disclose an outside sentinel under at least one actual Java probe. Consumer outcomes over the same six files are:

| Evidence condition | Unqualified false clearances | Scope-qualified false clearances | Qualified insufficient-evidence decisions |
| --- | ---: | ---: | ---: |
| Clean current | 0 | 0 | 0 |
| Stale previous revision | 0 | 0 | 6 |
| Partial current | 2 | 0 | 3 |
| Omitted rule, simulated | 4 | 0 | 6 |

The clean current scan reports five findings and clears only the constant-file fixture. The partial scan actually analyzes three files; qualification escalates the three omitted files. The omitted-rule condition is simulated with no Semgrep command, no required rule, and no findings. It is not a failed or silently incomplete Semgrep invocation. The stale report already raises six warnings, so qualification yields no false-clearance improvement there and exposes a conservative abstention cost.

The preserved observed evidence is in `results/observed/`. Workspace prefixes in published copies are replaced by `<WORKSPACE>`; numeric results are unchanged. `PUBLICATION_PROVENANCE.json` records original-source and published-file SHA-256 digests and the path-only transformation. Original run paths in manifests are provenance labels, not required directories in this repository. The standalone runner was also rerun during artifact preparation and matched all non-timing metrics.

## Regenerate the figures

`figure_data.json` is a small numeric snapshot independently checked against all 24 probes and 48 consumer decisions. The plot script runs no Java, analyzer, model inference, or training. To verify the snapshot's source identities and the included public files before plotting:

```sh
python generate_figures.py --verify-publication-root .
```

This creates `figures/probe_outcomes.png` and `figures/scope_outcomes.png`. To verify against an original unnormalized workspace instead, use `--verify-source-root /path/to/Amazon_Research_Proposals`. That original workspace is optional and is not needed to run the public artifact.

## Manuscript and Overleaf

The manuscript sources are bundled in `overleaf.zip`; the repository has no loose TeX or bibliography files. Upload that ZIP to Overleaf, select `draft.tex` as the main file, and use pdfLaTeX with BibTeX. `references.bib` is an identical compatibility copy; the manuscript reads only `refs.bib`. For a local TeX installation containing `acmart`, extract the ZIP into a new directory, change into it, and run:

```sh
latexmk -pdf -interaction=nonstopmode -halt-on-error draft.tex
```

The sections are Abstract, Introduction and Background, Methods, Results, Future Work, and Conclusion. The seven bibliography entries were checked against primary sources on October 31, 2026; the assurance-deference study is identified as a preprint.

## Scope

These six authored fixtures are not public CVEs or representative repository samples. Limited dynamic probes do not prove safety. The trusted harness captures revision, file, hash, and rule identity; forged manifests and malicious analyzers are untested. Correct scope does not repair semantic rule incompleteness. The observed reductions in false clearance result from explicit insufficient-evidence decisions, not new vulnerability detection. No LLM triage, targeted recovery, analyst-time, deployment performance, or population error-rate result is measured.
