"""Java/git provenance pilot. The built-in scanner is explicitly a toy lexical baseline."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import random
import shutil
import subprocess
from pathlib import Path
from pilots.common import PilotContext


SAFE = 'Path p = root.resolve(args[1]).normalize(); if (!p.startsWith(root)) { System.out.print("BLOCKED"); return; }'
BODIES = {
    "DirectResolve": 'Path p = root.resolve(args[1]);',
    "FileJoin": 'Path p = new java.io.File(args[0], args[1]).toPath();',
    "CheckedNormalize": SAFE,
    "DotDotFilter": 'if (args[1].contains("..")) { System.out.print("BLOCKED"); return; } Path p = root.resolve(args[1]);',
    "ConstantFile": 'Path p = root.resolve("inside.txt");',
    "StringPrefix": 'Path p = root.resolve(args[1]).normalize(); if (!p.toString().startsWith(root.toString())) { System.out.print("BLOCKED"); return; }',
}


def _java_source(name: str, body: str) -> str:
    return ('import java.nio.file.*;\npublic class ' + name + ' {\n'
            ' public static void main(String[] args) throws Exception {\n'
            '  Path root = Paths.get(args[0]).toAbsolutePath().normalize();\n  ' + body + '\n'
            '  System.out.print(new String(Files.readAllBytes(p), "UTF-8"));\n }\n}\n')


def _cmd(args: list[str], cwd: Path, timeout: float) -> dict:
    p = subprocess.run(args, cwd=str(cwd), text=True, capture_output=True, timeout=timeout)
    return {"argv": args, "returncode": p.returncode, "stdout": p.stdout, "stderr": p.stderr}


def _git(project: Path, args: list[str], timeout: float) -> str:
    command = ["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null",
               "-c", "user.name=Local pilot", "-c", "user.email=pilot@example.invalid", *args]
    r = _cmd(command, project, timeout)
    if r["returncode"]:
        raise RuntimeError("git fixture operation failed: " + r["stderr"])
    return r["stdout"].strip()


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _toy_scan(files: list[Path]) -> tuple[list[str], list[dict]]:
    """Deliberately limited source-pattern triage; not CodeQL, Semgrep, or sound analysis."""
    warnings = []
    for file in files:
        text = file.read_text()
        source_sink_shape = "root.resolve(args[1])" in text or "new java.io.File(args[0], args[1])" in text
        # The intentionally crude guard heuristic wrongly trusts String.startsWith.
        if source_sink_shape and ".startsWith(" not in text:
            warnings.append(file.name)
    return warnings, []


def _scan(files: list[Path], scanner: str, project: Path, rules: Path, timeout: float) -> tuple[list[str], list[dict]]:
    if scanner == "toy_lexical":
        return _toy_scan(files)
    executable = shutil.which("semgrep")
    if not executable:
        raise FileNotFoundError("PILOT03_SCANNER=semgrep requested, but semgrep is not installed; no automatic install or fake replacement")
    args = [executable, "scan", "--config", str(rules), "--json", "--metrics=off",
            "--disable-version-check", "--no-git-ignore", *[str(p) for p in files]]
    r = _cmd(args, project, timeout)
    if r["returncode"] not in (0, 1):
        raise RuntimeError("Semgrep failed: " + r["stderr"])
    report = json.loads(r["stdout"])
    if report.get("errors"):
        raise RuntimeError("Semgrep reported analysis errors: " + json.dumps(report["errors"]))
    warnings = sorted({Path(x["path"]).name for x in report.get("results", [])})
    return warnings, [r]


def _report(files: list[Path], scanner: str, project: Path, rules: Path, timeout: float,
            include_rule: bool = True) -> dict:
    warnings, commands = _scan(files, scanner, project, rules, timeout) if include_rule else ([], [])
    return {"revision": _git(project, ["rev-parse", "HEAD"], timeout),
            "source_hashes": {p.name: _hash(p) for p in files},
            "invoked_files": [p.name for p in files], "finding_files": warnings,
            "rule_ids": ["local-path-read"] if include_rule else [],
            "scanner": scanner, "commands": commands,
            "coverage_note": "File list and hashes are captured by this trusted local harness; not inferred from no findings."}



def _toolchain_preflight(timeout: float = 5) -> dict:
    """Do not execute Apple's tool stubs when their backing installation is absent.

    Custom Homebrew/jenv binaries keep their ordinary execution path. The two
    discovery commands used here report configuration; they do not start Apple's
    developer-tools or Java installation UI.
    """
    resolved = {name: shutil.which(name) for name in ("git", "javac", "java")}
    unavailable = [name + ": executable not found" for name, path in resolved.items() if not path]
    probes = []

    def probe(command: list[str]) -> dict:
        try:
            result = subprocess.run(command, capture_output=True, text=True,
                                    timeout=max(0.1, min(timeout, 5)))
            record = {"argv": command, "returncode": result.returncode,
                      "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}
        except (OSError, subprocess.TimeoutExpired) as exc:
            record = {"argv": command, "returncode": None, "stdout": "", "stderr": str(exc)}
        probes.append(record)
        return record

    if platform.system() == "Darwin":
        if resolved["git"] == "/usr/bin/git":
            selector = shutil.which("xcode-select")
            if not selector:
                unavailable.append("git: macOS stub found but xcode-select is unavailable; git was not invoked")
            else:
                result = probe([selector, "-p"])
                if result["returncode"] != 0 or not result["stdout"] or not Path(result["stdout"]).is_dir():
                    unavailable.append("git: no configured macOS developer tools; git was not invoked")
        if any(resolved[name] == "/usr/bin/" + name for name in ("java", "javac")):
            home_tool = shutil.which("/usr/libexec/java_home")
            if not home_tool:
                unavailable.append("Java: macOS stub found but java_home is unavailable; java/javac were not invoked")
            else:
                result = probe([home_tool])
                java_home = Path(result["stdout"]) if result["stdout"] else None
                if (result["returncode"] != 0 or java_home is None
                        or not (java_home / "bin" / "javac").is_file()):
                    unavailable.append("Java: no registered JDK with javac; java/javac were not invoked")
    return {"resolved_executables": resolved, "unavailable": unavailable, "configuration_probes": probes}


def run(ctx: PilotContext) -> dict:
    preflight = _toolchain_preflight(ctx.timeout_seconds)
    ctx.write_json("toolchain_preflight.json", preflight)
    if preflight["unavailable"]:
        return {"experiment_id": "03", "topic": "Amazon Security", "status": "skipped",
                "evidence_level": "dependency check only", "metrics": {"unavailable_tools": preflight["unavailable"]},
                "findings": [], "limitations": ["Install/configure a JDK and git before running the real Java effect oracle. macOS installation stubs were not executed."],
                "artifacts": ["toolchain_preflight.json"], "proposal_claim_template": "No empirical result is available until the dependency check and Java pilot run succeed."}
    timeout = max(10, min(ctx.timeout_seconds, 120))
    scanner_choice = os.environ.get("PILOT03_SCANNER", "toy_lexical")
    if scanner_choice not in ("toy_lexical", "semgrep"):
        raise ValueError("PILOT03_SCANNER must be toy_lexical or semgrep")
    if scanner_choice == "semgrep" and not shutil.which("semgrep"):
        return {"experiment_id": "03", "topic": "Amazon Security", "status": "skipped",
                "evidence_level": "dependency check only", "metrics": {"missing_tools": ["semgrep"]},
                "findings": [], "limitations": ["Requested real Semgrep mode was not run. No toy results are substituted for analyzer results."],
                "artifacts": [], "proposal_claim_template": "No real analyzer result is available until Semgrep is installed and the pilot succeeds."}
    project = ctx.path("java_project")
    src, classes = project / "src", project / "classes"
    src.mkdir(parents=True, exist_ok=True)
    classes.mkdir(exist_ok=True)
    init = _cmd(["git", "init", "--quiet"], project, timeout)
    if init["returncode"]:
        raise RuntimeError(init["stderr"])
    rules = ctx.path("path_read_rule.yml")
    rules.write_text('''rules:
  - id: local-path-read
    languages: [java]
    message: Untrusted command-line path reaches a file read (fixture taint rule)
    severity: WARNING
    mode: taint
    pattern-sources:
      - pattern: args[1]
    pattern-sinks:
      - pattern: Files.readAllBytes(...)
''')
    files = []
    for name in BODIES:
        path = src / (name + ".java")
        path.write_text(_java_source(name, SAFE))
        files.append(path)
    _git(project, ["add", "src"], timeout)
    _git(project, ["commit", "--allow-empty", "--quiet", "-m", "safe fixture baseline"], timeout)
    previous = _report(files, scanner_choice, project, rules, timeout)
    for name, body in BODIES.items():
        (src / (name + ".java")).write_text(_java_source(name, body))
    _git(project, ["add", "src"], timeout)
    _git(project, ["commit", "--allow-empty", "--quiet", "-m", "held-out source variants"], timeout)
    current_sha = _git(project, ["rev-parse", "HEAD"], timeout)
    compile_result = _cmd(["javac", "-d", str(classes), *[str(p) for p in files]], project, timeout)
    if compile_result["returncode"]:
        raise RuntimeError("Fixture javac compilation failed: " + compile_result["stderr"])
    sandbox = ctx.path("probe_sandbox")
    root = sandbox / "root"
    sibling = sandbox / "root_evil"
    root.mkdir(parents=True, exist_ok=True)
    sibling.mkdir(exist_ok=True)
    (root / "inside.txt").write_text("PUBLIC_INSIDE")
    (sandbox / "outside.txt").write_text("PRIVATE_OUTSIDE")
    (sibling / "outside.txt").write_text("PRIVATE_SIBLING")
    probes = [("legitimate", "inside.txt"), ("parent_escape", "../outside.txt"),
              ("absolute_escape", str(sandbox / "outside.txt")),
              ("prefix_sibling_escape", "../root_evil/outside.txt")]
    probe_rows, gold = [], {}
    for file in files:
        leaked = False
        for probe_name, argument in probes:
            r = _cmd(["java", "-Xmx128m", "-cp", str(classes), file.stem, str(root), argument], project, timeout)
            disclosure = "PRIVATE_" in r["stdout"]
            leaked = leaked or disclosure
            probe_rows.append({"file": file.name, "probe": probe_name, "input": argument,
                               "returncode": r["returncode"], "stdout": r["stdout"],
                               "stderr": r["stderr"], "target_disclosure_observed": disclosure})
        gold[file.name] = leaked
    full = _report(files, scanner_choice, project, rules, timeout)
    partial_files = random.Random(ctx.seed).sample(files, 3)
    partial = _report(partial_files, scanner_choice, project, rules, timeout)
    absent_rule = _report(files, scanner_choice, project, rules, timeout, include_rule=False)
    reports = {"clean_current": full, "stale_previous_revision": previous,
               "partial_current": partial, "omitted_rule_pack": absent_rule}
    rows = []
    for condition, report in reports.items():
        for file in files:
            reported_finding = file.name in report["finding_files"]
            naive = "finding" if reported_finding else "clear"
            checks = {"current_revision": report["revision"] == current_sha,
                      "file_in_invocation": file.name in report["invoked_files"],
                      "source_hash_matches": report["source_hashes"].get(file.name) == _hash(file),
                      "required_rule_present": "local-path-read" in report["rule_ids"]}
            qualified = "insufficient_evidence" if not all(checks.values()) else naive
            for arm, verdict in (("unqualified_report_consumer", naive), ("scope_qualified_consumer", qualified)):
                rows.append({"condition": condition, "file": file.name, "arm": arm,
                             "verdict": verdict, "target_disclosure_observed": gold[file.name],
                             "false_clearance": verdict == "clear" and gold[file.name],
                             "scope_checks": json.dumps(checks, sort_keys=True)})
    ctx.write_json("analysis_reports.json", reports)
    ctx.write_json("javac_command.json", compile_result)
    ctx.write_csv("java_probe_results.csv", probe_rows)
    ctx.write_csv("triage_results.csv", rows)
    metrics = {"scanner": scanner_choice, "fixture_files": len(files),
               "files_with_target_disclosure_observed": sum(gold.values()),
               "dynamic_probes": len(probe_rows), "conditions": {}}
    for condition in reports:
        metrics["conditions"][condition] = {}
        for arm in ("unqualified_report_consumer", "scope_qualified_consumer"):
            selected = [r for r in rows if r["condition"] == condition and r["arm"] == arm]
            metrics["conditions"][condition][arm] = {"false_clearances": sum(r["false_clearance"] for r in selected),
                "clearances": sum(r["verdict"] == "clear" for r in selected),
                "insufficient_evidence": sum(r["verdict"] == "insufficient_evidence" for r in selected),
                "reported_findings": sum(r["verdict"] == "finding" for r in selected)}
    return {"experiment_id": "03", "topic": "Amazon Security", "status": "completed",
        "evidence_level": "real Java execution and git-provenance fixture; " + ("real Semgrep with authored taint rule" if scanner_choice == "semgrep" else "toy lexical scanner, not a real security-analyzer result"),
        "metrics": metrics,
        "findings": ["Observed file disclosures come from actual compiled Java execution against local sentinel files.",
                     "No-finding results and evidence completeness are evaluated separately.",
                     "The current-revision String-prefix fixture tests whether a semantic scanner miss survives correct metadata; scope checks do not repair all missed vulnerabilities."],
        "limitations": ["These six authored fixtures and four probes are not public CVEs, representative repositories, or newly discovered vulnerabilities.",
                        "The default lexical checker is intentionally limited and must not be called CodeQL, Semgrep, sound static analysis, or validation of a full Java security agent.",
                        "Optional Semgrep uses a small authored local taint rule, not a validated comprehensive security rule pack; absence of a finding is not proof of safety.",
                        "The harness trusts its own git/build/invocation capture; malicious or incomplete provenance capture is not tested.",
                        "No model triage, large repository build, analyst workload study, or natural software-population miss rate is measured.",
                        "Held-out source variants share the path-traversal domain with development fixtures; this is source/provenance integration evidence, not learned generalization."],
        "artifacts": ["analysis_reports.json", "javac_command.json", "java_probe_results.csv", "triage_results.csv", "path_read_rule.yml", "toolchain_preflight.json"],
        "proposal_claim_template": "On [N] authored Java fixtures with [P] actual execution probes, [scanner mode] and [consumer] produced [false clearances] under [condition]. This supports provenance-harness feasibility only; real-repository security triage remains to be tested."}
