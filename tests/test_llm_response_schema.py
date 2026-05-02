"""
Tests del schema LLMResponse.

Cubre los contratos del JSON que el LLM se compromete a devolver, incluyendo
los casos donde alucina (devuelve shape inesperado) y la regla de negocio
de limpiar lead_data cuando lead_captured es false.
"""
import pytest
from pydantic import ValidationError
from schemas.models import LLMResponse


class TestNormalCases:
    def test_normal_response_without_lead_parses(self):
        raw = (
            '{"response": "Hola", "lead_captured": false, '
            '"lead_data": null, "request_detail": null, "cede_control": false}'
        )
        result = LLMResponse.model_validate_json(raw)
        assert result.response == "Hola"
        assert result.lead_captured is False
        assert result.lead_data is None
        assert result.cede_control is False

    def test_lead_captured_with_full_data_parses(self):
        raw = (
            '{"response": "Gracias!", "lead_captured": true, '
            '"lead_data": {"name": "Juan", "phone": "+5491100000", "email": "j@x.com"}, '
            '"request_detail": "consulta menu", "cede_control": true}'
        )
        result = LLMResponse.model_validate_json(raw)
        assert result.lead_captured is True
        assert result.lead_data is not None
        assert result.lead_data.name == "Juan"
        assert result.lead_data.phone == "+5491100000"
        assert result.lead_data.email == "j@x.com"
        assert result.cede_control is True

    def test_lead_data_minimal_only_name(self):
        # Según el schema LeadData, name es lo único requerido.
        raw = (
            '{"response": "ok", "lead_captured": true, '
            '"lead_data": {"name": "Maria"}, "cede_control": true}'
        )
        result = LLMResponse.model_validate_json(raw)
        assert result.lead_data.name == "Maria"
        assert result.lead_data.phone is None
        assert result.lead_data.email is None


class TestDefaults:
    def test_optional_fields_use_defaults(self):
        raw = '{"response": "ok"}'
        result = LLMResponse.model_validate_json(raw)
        assert result.lead_captured is False
        assert result.lead_data is None
        assert result.request_detail is None
        assert result.cede_control is False


class TestBusinessRule:
    """
    Regla de negocio: si lead_captured=False, lead_data debe forzarse a None
    aunque el LLM lo haya devuelto lleno (alucinación).
    """

    def test_lead_data_cleared_when_lead_captured_false(self):
        raw = (
            '{"response": "ok", "lead_captured": false, '
            '"lead_data": {"name": "Maria"}, "cede_control": false}'
        )
        result = LLMResponse.model_validate_json(raw)
        assert result.lead_captured is False
        assert result.lead_data is None  # debe quedar limpiado por el validator

    def test_lead_data_preserved_when_lead_captured_true(self):
        raw = (
            '{"response": "ok", "lead_captured": true, '
            '"lead_data": {"name": "Maria"}, "cede_control": true}'
        )
        result = LLMResponse.model_validate_json(raw)
        assert result.lead_data.name == "Maria"


class TestErrorCases:
    def test_malformed_json_raises(self):
        with pytest.raises((ValueError, ValidationError)):
            LLMResponse.model_validate_json('{response: "no quotes"}')

    def test_missing_required_response_field_raises(self):
        with pytest.raises(ValidationError):
            LLMResponse.model_validate_json(
                '{"lead_captured": false, "cede_control": false}'
            )

    def test_lead_data_with_missing_name_raises(self):
        # name es requerido en LeadData.
        with pytest.raises(ValidationError):
            LLMResponse.model_validate_json(
                '{"response": "ok", "lead_captured": true, '
                '"lead_data": {"phone": "+1234"}, "cede_control": true}'
            )
