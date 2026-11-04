"""Transparent weighted comparison, not an inferred chemical safety score."""

from .schemas import CRITERIA, Assessment, Weights


def rank_candidates(candidates: list[dict], weights: Weights, protocol: str) -> dict:
    ranked, incomplete = [], []
    w = weights.model_dump()
    for candidate in candidates:
        assessment = (
            Assessment.model_validate(candidate["assessment"])
            if candidate.get("assessment")
            else None
        )
        missing = [
            key
            for key in CRITERIA
            if w[key] > 0 and (not assessment or getattr(assessment, key) is None)
        ]
        if not assessment or assessment.comparison_protocol != protocol:
            missing.append("comparison_protocol")
        base = {
            "id": candidate["id"],
            "name": candidate["name"],
            "data_origin": candidate["data_origin"],
        }
        if missing:
            incomplete.append({**base, "missing": missing})
            continue
        contributions = {
            key: getattr(assessment, key).score * w[key] / 100 for key in CRITERIA if w[key] > 0
        }
        ranked.append(
            {
                **base,
                "score": round(sum(contributions.values()), 6),
                "contributions": contributions,
                "evidence": assessment.model_dump(),
            }
        )
    ranked.sort(key=lambda x: (-x["score"], x["id"]))
    last_score, rank = None, 0
    for index, row in enumerate(ranked, 1):
        if row["score"] != last_score:
            rank = index
        row["rank"] = rank
        last_score = row["score"]
    return {
        "ranked": ranked,
        "incomplete": incomplete,
        "weights": w,
        "protocol": protocol,
        "method": "Weighted sum v1: sum(score_0_100 * weight_percent / 100)",
        "scope": "Prioritas dari bukti tim; bukan sertifikasi keamanan atau efikasi.",
    }
