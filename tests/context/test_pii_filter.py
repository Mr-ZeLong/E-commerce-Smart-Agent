"""Tests for real-time PII detection and filtering."""

import pytest

from app.context.pii_filter import (
    GDPRComplianceManager,
    PIIDetectionResult,
    filter_dict,
    filter_text,
    log_pii_detection,
    pii_filter,
)


class TestCreditCardDetection:
    def test_visa_detected_and_redacted(self):
        text = "My card is 4111 1111 1111 1111"
        result = pii_filter.filter_text(text)
        assert result.has_pii
        assert "[CREDIT_CARD_REDACTED]" in result.redacted_text
        assert result.detections["credit_card"] == 1

    def test_mastercard_detected(self):
        text = "Card: 5555-5555-5555-4444"
        result = pii_filter.filter_text(text)
        assert result.has_pii
        assert result.detections["credit_card"] == 1

    def test_amex_detected(self):
        text = "Amex: 3782 822463 10005"
        result = pii_filter.filter_text(text)
        assert result.has_pii
        assert result.detections["credit_card"] == 1

    def test_invalid_luhn_not_redacted(self):
        text = "Card: 4111 1111 1111 1112"
        result = pii_filter.filter_text(text)
        assert not result.has_pii
        assert "4111" in result.redacted_text

    def test_short_digit_sequence_not_redacted(self):
        text = "Code: 123456789012"
        result = pii_filter.filter_text(text)
        assert not result.has_pii


class TestChineseMobileDetection:
    def test_chinese_mobile_detected(self):
        text = "Call me at 13800138000"
        result = pii_filter.filter_text(text)
        assert result.has_pii
        assert "[PHONE_REDACTED]" in result.redacted_text
        assert result.detections["phone"] == 1

    def test_chinese_mobile_with_country_code(self):
        text = "Contact: +86 138-0013-8000"
        result = pii_filter.filter_text(text)
        assert result.has_pii
        assert "[PHONE_REDACTED]" in result.redacted_text

    def test_chinese_mobile_with_spaces(self):
        text = "Phone: 138 0013 8000"
        result = pii_filter.filter_text(text)
        assert result.has_pii


class TestInternationalPhoneDetection:
    def test_international_phone_detected(self):
        text = "Call +1-234-567-8901"
        result = pii_filter.filter_text(text)
        assert result.has_pii
        assert "[PHONE_REDACTED]" in result.redacted_text

    def test_short_international_not_redacted(self):
        text = "Dial +123"
        result = pii_filter.filter_text(text)
        assert not result.has_pii


class TestChineseIDDetection:
    def test_valid_chinese_id_detected(self):
        text = "ID: 110101199003070038"
        result = pii_filter.filter_text(text)
        assert result.has_pii
        assert "[ID_REDACTED]" in result.redacted_text
        assert result.detections["chinese_id"] == 1

    def test_invalid_chinese_id_not_redacted(self):
        text = "ID: 110101199003070037"
        result = pii_filter.filter_text(text)
        assert not result.has_pii

    def test_chinese_id_with_x_checksum(self):
        text = "ID: 32010619900307024X"
        result = pii_filter.filter_text(text)
        assert result.has_pii
        assert "[ID_REDACTED]" in result.redacted_text


class TestPassportDetection:
    def test_passport_detected(self):
        text = "Passport: E12345678"
        result = pii_filter.filter_text(text)
        assert result.has_pii
        assert "[PASSPORT_REDACTED]" in result.redacted_text
        assert result.detections["passport"] == 1

    def test_nine_digit_passport(self):
        text = "Passport number 123456789"
        result = pii_filter.filter_text(text)
        assert result.has_pii


class TestEmailDetection:
    def test_email_detected(self):
        text = "Email: test@example.com"
        result = pii_filter.filter_text(text)
        assert result.has_pii
        assert "[EMAIL_REDACTED]" in result.redacted_text
        assert result.detections["email"] == 1

    def test_multiple_emails(self):
        text = "Contact a@b.com or c@d.org"
        result = pii_filter.filter_text(text)
        assert result.detections["email"] == 2


class TestPasswordDetection:
    def test_password_detected(self):
        text = "password: secret123"
        result = pii_filter.filter_text(text)
        assert result.has_pii
        assert "[PASSWORD_REDACTED]" in result.redacted_text
        assert result.detections["password"] == 1

    def test_password_with_equals(self):
        text = "password=supersecret"
        result = pii_filter.filter_text(text)
        assert result.has_pii

    def test_password_case_insensitive(self):
        text = "Password: MySecret"
        result = pii_filter.filter_text(text)
        assert result.has_pii


class TestSSNDetection:
    def test_ssn_detected(self):
        text = "SSN: 123-45-6789"
        result = pii_filter.filter_text(text)
        assert result.has_pii
        assert "[SSN_REDACTED]" in result.redacted_text
        assert result.detections["ssn"] == 1


class TestBankAccountDetection:
    def test_bank_account_with_context(self):
        text = "My bank account is 1234567890123456"
        result = pii_filter.filter_text(text)
        assert result.has_pii
        assert "[BANK_ACCOUNT_REDACTED]" in result.redacted_text

    def test_long_number_without_context(self):
        text = "1234567890123456"
        result = pii_filter.filter_text(text)
        assert result.has_pii

    def test_short_number_not_redacted(self):
        text = "Code: 12345678"
        result = pii_filter.filter_text(text)
        assert not result.has_pii


class TestMultiplePIITypes:
    def test_multiple_types_in_one_text(self):
        text = "Email: test@example.com, Phone: 13800138000, Card: 4111 1111 1111 1111"
        result = pii_filter.filter_text(text)
        assert result.has_pii
        assert result.detections["email"] == 1
        assert result.detections["phone"] == 1
        assert result.detections["credit_card"] == 1


class TestNoPII:
    def test_plain_text_no_pii(self):
        text = "Hello, I want to order a product."
        result = pii_filter.filter_text(text)
        assert not result.has_pii
        assert result.redacted_text == text

    def test_empty_string(self):
        result = pii_filter.filter_text("")
        assert not result.has_pii
        assert result.redacted_text == ""

    def test_none_input(self):
        result = pii_filter.filter_text(None)
        assert not result.has_pii
        assert result.redacted_text == ""


class TestDictionaryFiltering:
    def test_filter_dict_redacts_values(self):
        data = {
            "email": "test@example.com",
            "name": "Alice",
            "phone": "13800138000",
        }
        result = filter_dict(data)
        assert result["email"] == "[EMAIL_REDACTED]"
        assert result["name"] == "Alice"
        assert result["phone"] == "[PHONE_REDACTED]"

    def test_filter_dict_with_keys_param(self):
        data = {
            "email": "test@example.com",
            "name": "Alice",
        }
        result = filter_dict(data, keys=["email"])
        assert result["email"] == "[EMAIL_REDACTED]"
        assert result["name"] == "Alice"

    def test_filter_dict_nested(self):
        data = {
            "user": {
                "email": "test@example.com",
                "phone": "13800138000",
            }
        }
        result = filter_dict(data)
        assert result["user"]["email"] == "[EMAIL_REDACTED]"
        assert result["user"]["phone"] == "[PHONE_REDACTED]"

    def test_filter_dict_with_list(self):
        data = {
            "contacts": [
                {"email": "a@b.com"},
                {"email": "c@d.com"},
            ]
        }
        result = filter_dict(data)
        assert result["contacts"][0]["email"] == "[EMAIL_REDACTED]"
        assert result["contacts"][1]["email"] == "[EMAIL_REDACTED]"


class TestListFiltering:
    def test_filter_list_strings(self):
        items = ["Email: test@example.com", "Just text"]
        result = pii_filter.filter_list(items)
        assert "[EMAIL_REDACTED]" in result[0]
        assert result[1] == "Just text"

    def test_filter_list_nested_dicts(self):
        items = [
            {"email": "test@example.com"},
            {"phone": "13800138000"},
        ]
        result = pii_filter.filter_list(items)
        assert result[0]["email"] == "[EMAIL_REDACTED]"
        assert result[1]["phone"] == "[PHONE_REDACTED]"


class TestAsyncAPI:
    @pytest.mark.asyncio
    async def test_afilter_text(self):
        text = "Email: test@example.com"
        result = await pii_filter.afilter_text(text)
        assert result.has_pii
        assert "[EMAIL_REDACTED]" in result.redacted_text

    @pytest.mark.asyncio
    async def test_afilter_dict(self):
        data = {"email": "test@example.com"}
        result = await pii_filter.afilter_dict(data)
        assert result["email"] == "[EMAIL_REDACTED]"


class TestPIIDetectionResult:
    def test_result_fields(self):
        text = "Email: test@example.com"
        result = filter_text(text)
        assert isinstance(result, PIIDetectionResult)
        assert result.original_text == text
        assert result.has_pii
        assert "email" in result.detections


class TestLogPIIDetection:
    def test_log_with_detections(self, caplog):
        import logging

        with caplog.at_level(logging.WARNING):
            log_pii_detection(
                user_id=1,
                thread_id="thread-123",
                source="chat_input",
                detections={"email": 1, "phone": 2},
            )
        assert "PII detected and redacted" in caplog.text
        assert "email=1" in caplog.text
        assert "phone=2" in caplog.text

    def test_log_no_detections_no_log(self, caplog):
        import logging

        with caplog.at_level(logging.WARNING):
            log_pii_detection(
                user_id=1,
                thread_id="thread-123",
                source="chat_input",
                detections={},
            )
        assert "PII detected" not in caplog.text


class TestGDPRComplianceManager:
    def test_retention_not_expired(self):
        from datetime import UTC, datetime

        mgr = GDPRComplianceManager(retention_days=90)
        now = datetime.now(UTC).isoformat()
        assert not mgr.is_retention_expired(now)

    def test_retention_expired(self):
        from datetime import UTC, datetime, timedelta

        mgr = GDPRComplianceManager(retention_days=1)
        old = (datetime.now(UTC) - timedelta(days=2)).isoformat()
        assert mgr.is_retention_expired(old)

    def test_invalid_timestamp_returns_false(self):
        mgr = GDPRComplianceManager(retention_days=90)
        assert not mgr.is_retention_expired("not-a-timestamp")

    def test_default_retention_from_settings(self, monkeypatch):
        monkeypatch.setattr(
            "app.core.config.settings.MEMORY_RETENTION_DAYS", 30
        )
        mgr = GDPRComplianceManager()
        assert mgr.retention_days == 30

    @pytest.mark.asyncio
    async def test_delete_user_data_no_managers(self):
        mgr = GDPRComplianceManager(retention_days=90)
        result = await mgr.delete_user_data(user_id=1)
        assert result["user_id"] == 1
        assert result["deleted_vectors"] == 0
        assert result["deleted_structured"] == 0
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_delete_user_data_with_vector_manager(self):
        class FakeVectorManager:
            COLLECTION_NAME = "conversation_memory"

            async def ensure_collection(self):
                pass

            class FakeClient:
                async def scroll(self, **kwargs):
                    return [], None

            client = FakeClient()

        mgr = GDPRComplianceManager(retention_days=90)
        vm = FakeVectorManager()
        result = await mgr.delete_user_data(user_id=1, vector_manager=vm)
        assert result["deleted_vectors"] == 0
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_delete_user_data_vector_manager_error(self):
        class BrokenVectorManager:
            COLLECTION_NAME = "conversation_memory"

            async def ensure_collection(self):
                raise RuntimeError("boom")

        mgr = GDPRComplianceManager(retention_days=90)
        vm = BrokenVectorManager()
        result = await mgr.delete_user_data(user_id=1, vector_manager=vm)
        assert result["deleted_vectors"] == 0
        assert len(result["errors"]) == 1
        assert "boom" in result["errors"][0]


class TestModuleLevelConvenienceFunctions:
    def test_filter_text_convenience(self):
        result = filter_text("Email: test@example.com")
        assert result.has_pii

    def test_filter_dict_convenience(self):
        result = filter_dict({"email": "test@example.com"})
        assert result["email"] == "[EMAIL_REDACTED]"
