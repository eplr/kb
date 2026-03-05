#!/usr/bin/env python3
"""
TermIndex Knowledge Base — Compliance Analysis Pipeline

Loads a standard module (e.g., PCAF), accepts extracted institution data,
applies scoring rules, generates gap analysis, and outputs a compliance
assessment JSON.

Usage:
    python analyze.py --input institution_data.json --standard pcaf --output assessment.json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional


def load_json(path: Path) -> dict:
    """Load and parse a JSON file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: File not found: {path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {path}: {e}", file=sys.stderr)
        sys.exit(1)


def load_standard_module(standards_dir: Path, standard_id: str) -> dict:
    """Load all files for a given standard module."""
    standard_dir = standards_dir / standard_id

    if not standard_dir.exists():
        print(
            f"ERROR: Standard directory not found: {standard_dir}",
            file=sys.stderr,
        )
        sys.exit(1)

    return {
        "standard": load_json(standard_dir / "standard.json"),
        "scoring_rules": load_json(standard_dir / "scoring_rules.json"),
        "gap_analysis_rules": load_json(standard_dir / "gap_analysis_rules.json"),
    }


def get_applicable_parts(entity_type: str, standard: dict) -> list[str]:
    """Determine which PCAF parts apply to the entity type."""
    applicable = []
    for part in standard.get("parts", []):
        applicability = part.get("applicability", [])
        if entity_type in applicability or "all" in applicability:
            applicable.append(part["id"])
    return applicable


def count_asset_class_status(
    coverage: dict, status: str
) -> int:
    """Count how many asset classes have a given status."""
    return sum(1 for v in coverage.values() if v == status)


def score_asset_class_coverage(coverage: dict) -> int:
    """Score the asset_class_coverage criterion (0-5)."""
    reported = count_asset_class_status(coverage, "reported")
    partial = count_asset_class_status(coverage, "partial")
    total_covered = reported + partial

    if total_covered == 0:
        return 0
    elif total_covered <= 2:
        return 1
    elif total_covered <= 4:
        return 2
    elif total_covered <= 6:
        return 3
    elif total_covered <= 9:
        return 4
    else:
        return 5


def score_data_quality(dqs: Any) -> int:
    """Score the data_quality_score criterion based on DQS value."""
    if dqs is None:
        return 0

    # Handle string ranges like "1-5"
    if isinstance(dqs, str):
        try:
            parts = dqs.split("-")
            dqs = (float(parts[0]) + float(parts[-1])) / 2
        except (ValueError, IndexError):
            return 0

    try:
        dqs = float(dqs)
    except (ValueError, TypeError):
        return 0

    if dqs >= 4.5:
        return 1
    elif dqs >= 3.5:
        return 2
    elif dqs >= 2.5:
        return 3
    elif dqs >= 1.5:
        return 4
    else:
        return 5


def score_part_status(status: str) -> int:
    """Convert part status to a basic score indicator."""
    mapping = {"reported": 3, "partial": 1, "missing": 0, "N/A": -1}
    return mapping.get(status, 0)


def calculate_alternative_score(
    institution_data: dict,
    scoring_rules: dict,
) -> float:
    """Calculate the alternative (percentage-based) compliance score."""
    alt = scoring_rules.get("alternative_scoring", {})
    score = 0.0

    # PCAF status
    pcaf_status_scores = alt.get("pcaf_status", {})
    if institution_data.get("pcaf_signatory"):
        score += pcaf_status_scores.get("signatory", 0)
    elif institution_data.get("pcaf_mentioned"):
        score += pcaf_status_scores.get("mentioned", 0)

    # Part statuses
    part_status = institution_data.get("part_status", {})
    for part_key in ["part_a", "part_b", "part_c"]:
        alt_key = part_key.replace("part_", "part_")
        status = part_status.get(part_key, part_status.get(part_key.replace("part_", ""), "missing"))
        part_scores = alt.get(alt_key, {})
        score += part_scores.get(status, 0)

    # Asset class detail
    ac_scores = alt.get("asset_class_per_class", {})
    ac_coverage = institution_data.get("asset_class_coverage", {})
    for ac_status in ac_coverage.values():
        score += ac_scores.get(ac_status, 0)

    return round(score, 2)


def get_maturity_level(score: float, maturity_levels: list[dict]) -> dict:
    """Determine the maturity level based on score."""
    for level in maturity_levels:
        if level["min"] <= score <= level["max"]:
            return {
                "level": level["level"],
                "label": level["label"],
                "score": score,
            }
    return {"level": "unknown", "label": "Unknown", "score": score}


def identify_gaps(
    criteria_scores: list[dict],
    entity_type: str,
    gap_rules: dict,
) -> list[dict]:
    """Identify compliance gaps and classify by priority."""
    materiality = gap_rules.get("materiality_by_entity_type", {}).get(
        entity_type, {}
    )
    high_mat = set(materiality.get("high", []))
    medium_mat = set(materiality.get("medium", []))
    gap_templates = gap_rules.get("gap_templates", {})

    gaps = []
    for cs in criteria_scores:
        score = cs.get("score", 0)
        criterion_id = cs.get("id", "")

        if score >= 3:
            continue  # Low priority — not flagged as a gap

        # Determine materiality
        is_high = any(
            criterion_id in term or term in criterion_id for term in high_mat
        )
        is_medium = any(
            criterion_id in term or term in criterion_id for term in medium_mat
        )

        if score <= 1 and is_high:
            priority = "critical"
            timeline = "0-3 months"
        elif score <= 1 and is_medium:
            priority = "high"
            timeline = "3-6 months"
        elif score <= 1:
            priority = "high"
            timeline = "3-6 months"
        else:
            priority = "medium"
            timeline = "6-12 months"

        # Find matching gap template
        template_id = None
        template = {}
        for tid, tmpl in gap_templates.items():
            if criterion_id in tid or tid in criterion_id:
                template_id = tid
                template = tmpl
                break

        gaps.append(
            {
                "criterion_id": criterion_id,
                "priority": priority,
                "current_score": score,
                "target_score": min(score + 2, 5),
                "gap_template": template_id,
                "description": template.get(
                    "description", f"Score {score}/5 on {cs.get('name', criterion_id)}"
                ),
                "recommendation": template.get(
                    "recommendation",
                    f"Improve {cs.get('name', criterion_id)} from score {score} to {min(score + 2, 5)}",
                ),
                "timeline": timeline,
            }
        )

    # Sort by priority
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    gaps.sort(key=lambda g: priority_order.get(g["priority"], 99))

    return gaps


def analyze_institution(
    institution_data: dict,
    standard_module: dict,
) -> dict:
    """Perform full compliance analysis on an institution."""
    scoring_rules = standard_module["scoring_rules"]
    gap_rules = standard_module["gap_analysis_rules"]
    standard = standard_module["standard"]

    entity_type = institution_data.get("entity_type", "unknown")
    pcaf_data = institution_data.get("standards", {}).get("pcaf", institution_data)

    # Determine applicable parts
    applicable_parts = get_applicable_parts(entity_type, standard)

    # Score criteria
    ac_coverage = pcaf_data.get("asset_class_coverage", {})
    dqs = pcaf_data.get("dqs")
    part_status = pcaf_data.get("part_status", {})

    criteria_scores = []

    # Part A criteria (always applicable)
    if "A" in applicable_parts:
        criteria_scores.extend(
            [
                {
                    "id": "asset_class_coverage",
                    "part": "A",
                    "name": "Asset Class Coverage",
                    "score": score_asset_class_coverage(ac_coverage),
                    "max_score": 5,
                },
                {
                    "id": "data_quality_score",
                    "part": "A",
                    "name": "Data Quality Score",
                    "score": score_data_quality(dqs),
                    "max_score": 5,
                },
                {
                    "id": "attribution_methodology",
                    "part": "A",
                    "name": "Attribution Methodology",
                    "score": max(score_part_status(part_status.get("A", "missing")), 0),
                    "max_score": 5,
                },
                {
                    "id": "scope_coverage",
                    "part": "A",
                    "name": "Scope Coverage",
                    "score": max(score_part_status(part_status.get("A", "missing")), 0),
                    "max_score": 5,
                },
                {
                    "id": "portfolio_coverage",
                    "part": "A",
                    "name": "Portfolio Coverage",
                    "score": max(score_part_status(part_status.get("A", "missing")), 0),
                    "max_score": 5,
                },
                {
                    "id": "sovereign_debt_inclusion",
                    "part": "A",
                    "name": "Sovereign Debt Inclusion",
                    "score": (
                        2
                        if ac_coverage.get("sovereign_debt") == "reported"
                        else 1
                        if ac_coverage.get("sovereign_debt") == "partial"
                        else 0
                    ),
                    "max_score": 5,
                },
                {
                    "id": "temporal_coverage",
                    "part": "A",
                    "name": "Temporal Coverage",
                    "score": 1 if part_status.get("A") in ("reported", "partial") else 0,
                    "max_score": 5,
                },
                {
                    "id": "intensity_metrics",
                    "part": "A",
                    "name": "Intensity Metrics",
                    "score": 1 if part_status.get("A") == "reported" else 0,
                    "max_score": 5,
                },
            ]
        )

    # Part B criteria
    if "B" in applicable_parts:
        b_status = part_status.get("B", "N/A")
        criteria_scores.extend(
            [
                {
                    "id": "capital_markets_activity",
                    "part": "B",
                    "name": "Capital Markets Activity",
                    "score": max(score_part_status(b_status), 0),
                    "max_score": 5,
                },
                {
                    "id": "emission_attribution",
                    "part": "B",
                    "name": "Emission Attribution",
                    "score": max(score_part_status(b_status), 0),
                    "max_score": 5,
                },
            ]
        )

    # Part C criteria
    if "C" in applicable_parts:
        c_status = part_status.get("C", "N/A")
        c_score = max(score_part_status(c_status), 0)
        criteria_scores.extend(
            [
                {"id": "insurance_lines_coverage", "part": "C", "name": "Insurance Lines Coverage", "score": c_score, "max_score": 5},
                {"id": "commercial_lines", "part": "C", "name": "Commercial Lines", "score": c_score, "max_score": 5},
                {"id": "motor_insurance", "part": "C", "name": "Motor Insurance", "score": c_score, "max_score": 5},
                {"id": "project_insurance", "part": "C", "name": "Project Insurance", "score": c_score, "max_score": 5},
                {"id": "treaty_reinsurance", "part": "C", "name": "Treaty Reinsurance", "score": c_score, "max_score": 5},
                {"id": "attribution_methodology_c", "part": "C", "name": "Attribution Methodology", "score": c_score, "max_score": 5},
                {"id": "underwriting_integration", "part": "C", "name": "Underwriting Integration", "score": c_score, "max_score": 5},
                {"id": "data_quality_c", "part": "C", "name": "Data Quality", "score": c_score, "max_score": 5},
            ]
        )

    # Calculate part scores
    weighting = scoring_rules.get("weighting", {}).get(entity_type, {"part_a": 1.0})
    part_scores = {}

    for part_id in ["A", "B", "C"]:
        part_criteria = [cs for cs in criteria_scores if cs["part"] == part_id]
        if part_criteria:
            total = sum(cs["score"] for cs in part_criteria)
            max_total = sum(cs["max_score"] for cs in part_criteria)
            raw_pct = round((total / max_total) * 100, 2) if max_total > 0 else 0
            weight = weighting.get(f"part_{part_id.lower()}", 0)
            part_scores[part_id] = {
                "raw_percentage": raw_pct,
                "weighted_contribution": round(raw_pct * weight, 2),
            }

    weighted_score = round(
        sum(ps["weighted_contribution"] for ps in part_scores.values()), 2
    )

    # Alternative score
    flat_data = {
        "pcaf_signatory": pcaf_data.get("pcaf_signatory", False),
        "pcaf_mentioned": pcaf_data.get("pcaf_mentioned", False),
        "part_status": {
            "part_a": part_status.get("A", "missing"),
            "part_b": part_status.get("B", "N/A"),
            "part_c": part_status.get("C", "N/A"),
        },
        "asset_class_coverage": ac_coverage,
    }
    alternative_score = calculate_alternative_score(flat_data, scoring_rules)

    # Maturity level
    maturity = get_maturity_level(
        alternative_score, scoring_rules.get("maturity_levels", [])
    )

    # Gap analysis
    gaps = identify_gaps(criteria_scores, entity_type, gap_rules)

    # Summary
    strengths = []
    weaknesses = []
    if pcaf_data.get("pcaf_signatory"):
        strengths.append("PCAF signatory")
    if part_status.get("A") == "reported":
        strengths.append("Part A financed emissions reported")
    if score_asset_class_coverage(ac_coverage) >= 3:
        strengths.append("Good asset class coverage")

    critical_gaps = [g for g in gaps if g["priority"] == "critical"]
    high_gaps = [g for g in gaps if g["priority"] == "high"]
    if critical_gaps:
        weaknesses.extend([g["description"][:80] for g in critical_gaps[:3]])
    if high_gaps:
        weaknesses.extend([g["description"][:80] for g in high_gaps[:3]])

    priority_actions = [g["recommendation"][:100] for g in gaps[:5]]

    return {
        "institution_id": institution_data.get(
            "institution_id", institution_data.get("institution_metadata", {}).get("institution_name", "unknown")
        ),
        "standard_id": scoring_rules.get("standard_id", "pcaf"),
        "assessment_date": pcaf_data.get("assessment_date", ""),
        "entity_type": entity_type,
        "criteria_scores": criteria_scores,
        "part_scores": part_scores,
        "weighted_score": weighted_score,
        "alternative_score": alternative_score,
        "maturity": maturity,
        "gaps": gaps,
        "summary": {
            "strengths": strengths,
            "weaknesses": weaknesses,
            "priority_actions": priority_actions,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="TermIndex Knowledge Base — Compliance Analysis Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python analyze.py --input institution_data.json --standard pcaf --output assessment.json
    python analyze.py --input profiles/aviva.json --standard pcaf
        """,
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to extracted institution data JSON",
    )
    parser.add_argument(
        "--standard",
        default="pcaf",
        help="Standard ID to assess against (default: pcaf)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output file path for assessment JSON (default: stdout)",
    )
    parser.add_argument(
        "--standards-dir",
        default=None,
        help="Path to standards directory (default: auto-detect from script location)",
    )

    args = parser.parse_args()

    # Determine standards directory
    if args.standards_dir:
        standards_dir = Path(args.standards_dir)
    else:
        # Auto-detect: assume script is in pipeline/, standards is sibling
        script_dir = Path(__file__).parent
        standards_dir = script_dir.parent / "standards"

    # Load standard module
    print(f"Loading standard module: {args.standard}", file=sys.stderr)
    standard_module = load_standard_module(standards_dir, args.standard)

    # Load institution data
    print(f"Loading institution data from: {args.input}", file=sys.stderr)
    institution_data = load_json(Path(args.input))

    # Run analysis
    print("Running compliance analysis...", file=sys.stderr)
    assessment = analyze_institution(institution_data, standard_module)

    # Output
    output_json = json.dumps(assessment, indent=2, ensure_ascii=False)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"Assessment written to: {args.output}", file=sys.stderr)
    else:
        print(output_json)

    # Print summary to stderr
    maturity = assessment.get("maturity", {})
    print(
        f"\nResult: Score {assessment['alternative_score']}% — "
        f"Maturity {maturity.get('level', '?')} ({maturity.get('label', '?')})",
        file=sys.stderr,
    )
    print(f"Gaps identified: {len(assessment.get('gaps', []))}", file=sys.stderr)


if __name__ == "__main__":
    main()
