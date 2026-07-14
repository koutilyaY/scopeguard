"""Upload validation, filename sanitisation, citation verification, JSON repair."""

import pytest
from fastapi import HTTPException

from app.services.citations import quotation_in_source, verify_citation
from app.services.files import get_extension, sanitize_filename, validate_upload
from app.services.llm.base import extract_json

PDF_BYTES = b"%PDF-1.4 fake body ................................................"


class TestFilenames:
    def test_path_traversal_stripped(self):
        assert "/" not in sanitize_filename("../../etc/passwd")
        assert sanitize_filename("..\\..\\windows\\system32.pdf").endswith(".pdf")

    def test_special_characters_removed(self):
        assert sanitize_filename("inv<script>.pdf") == "inv_script_.pdf"

    def test_extension_allowlist(self):
        assert get_extension("contract.pdf") == ".pdf"
        assert get_extension("contract.PDF") == ".pdf"
        assert get_extension("malware.exe") == ""
        assert get_extension("archive.tar.gz") == ""


class TestUploadValidation:
    def test_valid_pdf(self):
        name, ext = validate_upload("contract.pdf", "application/pdf", PDF_BYTES)
        assert ext == ".pdf"

    def test_empty_file_rejected(self):
        with pytest.raises(HTTPException) as exc:
            validate_upload("contract.pdf", "application/pdf", b"")
        assert exc.value.status_code == 400

    def test_oversized_rejected(self):
        big = b"a" * (26 * 1024 * 1024)
        with pytest.raises(HTTPException) as exc:
            validate_upload("contract.txt", "text/plain", big)
        assert exc.value.status_code == 413

    def test_unsupported_extension_rejected(self):
        with pytest.raises(HTTPException) as exc:
            validate_upload("run.exe", "application/octet-stream", b"MZ....")
        assert exc.value.status_code == 415

    def test_mime_mismatch_rejected(self):
        with pytest.raises(HTTPException) as exc:
            validate_upload("contract.pdf", "text/html", PDF_BYTES)
        assert exc.value.status_code == 415

    def test_magic_bytes_checked(self):
        with pytest.raises(HTTPException) as exc:
            validate_upload("contract.pdf", "application/pdf", b"<html>not a pdf</html>")
        assert exc.value.status_code == 415


class TestCitations:
    SOURCE = "Onboarding of new source systems is excluded from the fixed fee."

    def test_verbatim_quote_accepted(self):
        assert quotation_in_source("new source systems is excluded", self.SOURCE)

    def test_whitespace_and_case_normalized(self):
        assert quotation_in_source("NEW   source systems\nis excluded", self.SOURCE)

    def test_fabricated_quote_rejected(self):
        assert not quotation_in_source("all Salesforce work is free of charge", self.SOURCE)

    def test_unknown_entity_id_rejected(self):
        check = verify_citation("nonexistent-id", "anything", {"real-id": self.SOURCE})
        assert not check.valid
        assert "Unknown entity" in check.reason

    def test_known_id_with_fabricated_quote_rejected(self):
        check = verify_citation("real-id", "fabricated words", {"real-id": self.SOURCE})
        assert not check.valid


class TestJsonExtraction:
    def test_plain_json(self):
        assert extract_json('{"a": 1}') == {"a": 1}

    def test_fenced_json(self):
        assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_json_with_prose(self):
        assert extract_json('Here you go: {"a": 1} hope that helps!') == {"a": 1}

    def test_think_blocks_stripped(self):
        assert extract_json('<think>reasoning...</think>{"a": 1}') == {"a": 1}

    def test_garbage_raises(self):
        with pytest.raises(ValueError):
            extract_json("no json here at all")
