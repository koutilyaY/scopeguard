"""Import row validation: bad dates, negative time, oversized days, unknown status."""

from app.services.imports import (
    parse_tabular,
    validate_invoice_rows,
    validate_time_entry_rows,
    validate_work_item_rows,
)

TS_MAPPING = {
    "employee_name": "Employee",
    "employee_role": "Role",
    "work_date": "Date",
    "hours": "Hours",
    "description": "Description",
    "billable_status": "Billable",
    "work_item_external_id": "Work Item",
}


def ts_row(**overrides) -> dict:
    row = {
        "Employee": "Priya Raman",
        "Role": "Data Engineer",
        "Date": "2025-06-05",
        "Hours": "6",
        "Description": "Salesforce auth setup",
        "Billable": "yes",
        "Work Item": "DE-106",
    }
    row.update(overrides)
    return row


class TestTimesheetValidation:
    def test_valid_row(self):
        valid, errors, warnings = validate_time_entry_rows([ts_row()], TS_MAPPING)
        assert len(valid) == 1 and not errors
        assert valid[0]["minutes"] == 360

    def test_negative_time_rejected(self):
        valid, errors, _ = validate_time_entry_rows([ts_row(Hours="-2")], TS_MAPPING)
        assert not valid
        assert errors[0].field == "hours"

    def test_zero_time_rejected(self):
        _, errors, _ = validate_time_entry_rows([ts_row(Hours="0")], TS_MAPPING)
        assert errors

    def test_unparseable_date_rejected(self):
        _, errors, _ = validate_time_entry_rows([ts_row(Date="not-a-date")], TS_MAPPING)
        assert errors[0].field == "work_date"

    def test_impossible_date_rejected(self):
        _, errors, _ = validate_time_entry_rows([ts_row(Date="1897-01-01")], TS_MAPPING)
        assert errors

    def test_excessive_daily_hours_warns(self):
        rows = [ts_row(Hours="10"), ts_row(Hours="9")]
        valid, errors, warnings = validate_time_entry_rows(rows, TS_MAPPING)
        assert len(valid) == 2
        assert any("exceeds" in w.message for w in warnings)

    def test_missing_employee_rejected_with_row_number(self):
        _, errors, _ = validate_time_entry_rows([ts_row(Employee="")], TS_MAPPING)
        assert errors[0].row == 2  # header is row 1

    def test_minutes_column_preferred(self):
        mapping = dict(TS_MAPPING, minutes="Minutes")
        valid, _, _ = validate_time_entry_rows([dict(ts_row(), Minutes="90")], mapping)
        assert valid[0]["minutes"] == 90


class TestWorkItemValidation:
    MAPPING = {
        "external_id": "Issue key",
        "title": "Summary",
        "status": "Status",
        "work_type": "Issue Type",
        "assignee": "Assignee",
        "created_at": "Created",
        "completed_at": "Resolved",
        "description": "Description",
        "source_url": "URL",
    }

    def wi_row(self, **overrides) -> dict:
        row = {
            "Issue key": "DE-106",
            "Summary": "Salesforce onboarding",
            "Status": "Done",
            "Issue Type": "Story",
            "Assignee": "Priya",
            "Created": "2025-06-01",
            "Resolved": "2025-06-25",
            "Description": "Build pipeline",
            "URL": "",
        }
        row.update(overrides)
        return row

    def test_valid_row(self):
        valid, errors, _ = validate_work_item_rows([self.wi_row()], self.MAPPING)
        assert len(valid) == 1 and not errors

    def test_missing_id_rejected(self):
        _, errors, _ = validate_work_item_rows([self.wi_row(**{"Issue key": ""})], self.MAPPING)
        assert errors

    def test_unknown_status_warns_and_defaults(self):
        valid, _, warnings = validate_work_item_rows(
            [self.wi_row(Status="Blocked-ish")], self.MAPPING
        )
        assert valid[0]["status"].value == "open"
        assert warnings

    def test_duplicate_id_in_file_skipped(self):
        valid, _, warnings = validate_work_item_rows([self.wi_row(), self.wi_row()], self.MAPPING)
        assert len(valid) == 1
        assert warnings


class TestInvoiceValidation:
    MAPPING = {
        "invoice_number": "Invoice",
        "issue_date": "Date",
        "status": "Status",
        "currency": "Currency",
        "line_description": "Item",
        "amount": "Amount",
        "quantity": "Qty",
        "unit_price": "Unit Price",
        "billing_period_start": "From",
        "billing_period_end": "To",
        "service_category": "Category",
        "work_item_external_id": "Work Item",
    }

    def inv_row(self, **overrides) -> dict:
        row = {
            "Invoice": "INV-100",
            "Date": "2025-06-28",
            "Status": "issued",
            "Currency": "USD",
            "Item": "Fixed fee",
            "Amount": "$85,000.00",
            "Qty": "1",
            "Unit Price": "$85,000.00",
            "From": "2025-06-01",
            "To": "2025-06-30",
            "Category": "fixed_fee",
            "Work Item": "",
        }
        row.update(overrides)
        return row

    def test_money_parsed_to_minor_units(self):
        valid, errors, _ = validate_invoice_rows([self.inv_row()], self.MAPPING)
        assert not errors
        assert valid[0]["amount_minor"] == 8_500_000

    def test_bad_amount_rejected(self):
        _, errors, _ = validate_invoice_rows([self.inv_row(Amount="lots")], self.MAPPING)
        assert errors


def test_parse_tabular_csv_roundtrip():
    csv_bytes = b"Employee,Date,Hours\nPriya,2025-06-05,6\nMarco,2025-06-06,7\n"
    columns, rows = parse_tabular("sheet.csv", csv_bytes)
    assert columns == ["Employee", "Date", "Hours"]
    assert rows[1]["Employee"] == "Marco"
