from __future__ import annotations

from datetime import date, datetime, timezone

from app.models.outputs import ClassificationResult, PriorityLevel
from app.models.records import PipelineRecord, PipelineStage, RecordType


NOTE_SIGNAL_MAP = {
    "champion left": "champion_left",
    "budget confirmed": "budget_confirmed",
    "requested demo": "requested_demo",
    "no response": "no_response",
    "competitor": "competitor_mentioned",
}


def infer_note_signals(notes: str | None) -> list[str]:
    lowered = (notes or "").lower()
    return [signal for phrase, signal in NOTE_SIGNAL_MAP.items() if phrase in lowered]


def classify_record(record: PipelineRecord) -> ClassificationResult:
    score = 20
    risk_flags: list[str] = []
    evidence: list[str] = []
    intent_signals = infer_note_signals(record.notes)

    if record.record_type == RecordType.OPPORTUNITY:
        score += 20
        evidence.append("Opportunity records receive a higher base score.")

    if record.annual_contract_value >= 50000:
        score += 20
        evidence.append("High ACV opportunity.")
    elif record.annual_contract_value >= 15000:
        score += 10
        evidence.append("Mid-market ACV potential.")

    if record.days_in_stage >= 21 and record.stage not in {PipelineStage.CLOSED_LOST, PipelineStage.CLOSED_WON}:
        score += 15
        risk_flags.append("stalled_stage")
        evidence.append("Record has been stuck in-stage for 21+ days.")

    if record.last_activity_at:
        days_since_activity = (datetime.now(timezone.utc) - record.last_activity_at.replace(tzinfo=timezone.utc)).days
        if days_since_activity >= 10:
            score += 8
            risk_flags.append("stale_activity")
            evidence.append("No recent seller activity in 10+ days.")

    if record.close_date and (record.close_date - date.today()).days <= 14 and not record.next_step:
        score += 15
        risk_flags.append("no_next_step_near_close")
        evidence.append("Close date is near but next step is empty.")

    if "budget_confirmed" in intent_signals:
        score += 6
        evidence.append("Buyer indicated budget alignment.")
    if "requested_demo" in intent_signals:
        score += 6
        evidence.append("Buyer asked for a demo.")
    if "champion_left" in intent_signals:
        score += 10
        risk_flags.append("champion_left")
        evidence.append("Internal champion may have left the account.")
    if "no_response" in intent_signals:
        score += 8
        risk_flags.append("unresponsive_buyer")
        evidence.append("Notes mention lack of buyer response.")
    if "competitor_mentioned" in intent_signals:
        score += 5
        risk_flags.append("competitive_pressure")
        evidence.append("Competitive pressure is present.")

    if not record.next_step:
        score += 5
        risk_flags.append("missing_next_step")
        evidence.append("Next step is missing.")

    score = min(score, 100)
    urgent_risk_flags = {"no_next_step_near_close", "champion_left"}
    escalation_risk_flags = {"competitive_pressure", "stalled_stage", "missing_next_step"}
    urgent_combination = bool(urgent_risk_flags.intersection(risk_flags)) or len(
        escalation_risk_flags.intersection(risk_flags)
    ) >= 2

    if score >= 80 and urgent_combination:
        priority = PriorityLevel.P1
    elif score >= 50:
        priority = PriorityLevel.P2
    else:
        priority = PriorityLevel.P3

    return ClassificationResult(
        record_id=record.record_id,
        priority_level=priority,
        score=score,
        risk_flags=sorted(set(risk_flags)),
        intent_signals=sorted(set(intent_signals)),
        evidence=evidence,
    )
