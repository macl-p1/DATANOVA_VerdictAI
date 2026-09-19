from __future__ import annotations


def render_metrics(metrics: dict) -> str:
    lines = ["VERDICTAI MODEL EVALUATION", "==========================", "", "ENTITY                  PRECISION   RECALL   F1", "------------------------------------------------"]
    for name, values in metrics.get("per_entity", {}).items():
        lines.append(f"{name:<23} {values['precision']:.3f}       {values['recall']:.3f}    {values['f1']:.3f}")
    overall = metrics.get("micro", {})
    lines.extend(["------------------------------------------------", f"Micro F1: {overall.get('f1', 0):.3f}"])
    return "\n".join(lines)
