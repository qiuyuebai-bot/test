import json
from pathlib import Path


def _roc_point(rows, threshold):
    positives = [row for row in rows if row["label"] == 1]
    negatives = [row for row in rows if row["label"] == 0]
    true_positive = sum(row["similarity"] >= threshold for row in positives)
    false_positive = sum(row["similarity"] >= threshold for row in negatives)
    return {
        "threshold": threshold,
        "true_positive_rate": true_positive / len(positives),
        "false_positive_rate": false_positive / len(negatives),
    }


def test_default_relevance_thresholds_have_stable_roc_points():
    fixture = Path(__file__).parent / "fixtures" / "hallucination_claims.json"
    rows = json.loads(fixture.read_text(encoding="utf-8"))
    assert _roc_point(rows, 0.50) == {"threshold": 0.50, "true_positive_rate": 1.0, "false_positive_rate": 2 / 3}
    assert _roc_point(rows, 0.70) == {"threshold": 0.70, "true_positive_rate": 1.0, "false_positive_rate": 1 / 3}

