from app.tools.validators import validate_pipeline_rows


def _valid_row() -> dict[str, str]:
    return {
        "record_id": "O-1",
        "record_type": "opportunity",
        "company_name": "Acme Co",
        "owner": "Alicia",
        "stage": "proposal",
        "source": "inbound",
        "annual_contract_value": "25000",
        "days_in_stage": "12",
        "last_activity_at": "2026-03-10T15:00:00",
        "next_step": "Schedule pricing review",
        "close_date": "2026-03-28",
        "contact_title": "VP Finance",
        "notes": "Budget confirmed.",
    }


def test_validate_pipeline_rows_collects_missing_columns():
    rows = [{"record_id": "1", "record_type": "lead"}]
    records, issues = validate_pipeline_rows(rows)

    assert records == []
    assert len(issues) == 1
    assert "missing columns" in issues[0].message


def test_validate_pipeline_rows_rejects_malformed_date():
    row = _valid_row()
    row["last_activity_at"] = "not-a-date"

    records, issues = validate_pipeline_rows([row])

    assert records == []
    assert len(issues) == 1
    assert "valid datetime" in issues[0].message.lower()


def test_validate_pipeline_rows_rejects_invalid_numeric_field():
    row = _valid_row()
    row["annual_contract_value"] = "-100"

    records, issues = validate_pipeline_rows([row])

    assert records == []
    assert len(issues) == 1
    assert "greater than or equal to 0" in issues[0].message


def test_validate_pipeline_rows_rejects_invalid_stage():
    row = _valid_row()
    row["stage"] = "pipeline_magic"

    records, issues = validate_pipeline_rows([row])

    assert records == []
    assert len(issues) == 1
    assert "input should be" in issues[0].message.lower()


def test_validate_pipeline_rows_normalizes_partial_but_valid_messiness():
    row = _valid_row()
    row["company_name"] = "  Acme Co  "
    row["source"] = "  inbound  "
    row["next_step"] = "  Send pricing follow-up  "
    row["contact_title"] = "   "
    row["notes"] = "  Budget confirmed.  "

    records, issues = validate_pipeline_rows([row])

    assert issues == []
    assert len(records) == 1
    assert records[0].company_name == "Acme Co"
    assert records[0].source == "inbound"
    assert records[0].next_step == "Send pricing follow-up"
    assert records[0].contact_title is None
    assert records[0].notes == "Budget confirmed."
