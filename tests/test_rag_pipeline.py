"""
Tests for the RAGPipeline service.
Tests RAG functionality, document indexing, and query processing.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.services.rag_pipeline import RAGPipeline, RAGResponse
from src.services.granite_client import GraniteClient


@pytest.fixture
def mock_granite_client():
    """Create a mock GraniteClient."""
    with patch.object(GraniteClient, '_check_ollama_available', return_value=False):
        client = GraniteClient(enable_cache=False)
    return client


@pytest.fixture
def rag_pipeline(mock_granite_client):
    """Create a RAGPipeline with mocked dependencies."""
    return RAGPipeline(granite_client=mock_granite_client)


@pytest.fixture
def sample_parsed_data():
    """Sample parsed OBD data for testing."""
    return {
        "metrics": [
            {
                "name": "engine_rpm",
                "value": 2500,
                "unit": "RPM",
                "status": "normal",
                "description": "Engine revolutions per minute",
                "normal_range": "600-7000"
            },
            {
                "name": "coolant_temp",
                "value": 95,
                "unit": "\u00b0C",
                "status": "normal",
                "description": "Engine coolant temperature",
                "normal_range": "70-105"
            },
            {
                "name": "engine_load",
                "value": 85,
                "unit": "%",
                "status": "warning",
                "description": "Engine load percentage",
                "normal_range": "0-80"
            }
        ],
        "fault_codes": [
            {
                "code": "P0300",
                "description": "Random/Multiple Cylinder Misfire Detected",
                "severity": "critical",
                "category": "powertrain",
                "possible_causes": ["Spark plugs", "Ignition coils"],
                "recommended_action": "Stop driving immediately"
            }
        ],
        "statistics": {
            "total_rows": 100,
            "metrics_count": 3,
            "normal_count": 2,
            "warning_count": 1,
            "critical_count": 0
        }
    }


@pytest.fixture
def healthy_parsed_data():
    """Sample healthy vehicle data for testing."""
    return {
        "metrics": [
            {
                "name": "engine_rpm",
                "value": 850,
                "unit": "RPM",
                "status": "normal",
                "description": "Engine revolutions per minute",
                "normal_range": "600-7000"
            },
            {
                "name": "coolant_temp",
                "value": 90,
                "unit": "\u00b0C",
                "status": "normal",
                "description": "Engine coolant temperature",
                "normal_range": "70-105"
            }
        ],
        "fault_codes": [],
        "statistics": {
            "total_rows": 50,
            "metrics_count": 2,
            "normal_count": 2,
            "warning_count": 0,
            "critical_count": 0
        }
    }


class TestRAGPipelineInitialization:
    """Tests for RAGPipeline initialization."""

    def test_pipeline_initialization(self, rag_pipeline):
        """Test pipeline initializes correctly."""
        assert rag_pipeline.granite is not None
        assert rag_pipeline.severity_classifier is not None
        assert isinstance(rag_pipeline._vector_stores, dict)

    def test_pipeline_with_custom_client(self):
        """Test pipeline accepts custom GraniteClient."""
        with patch.object(GraniteClient, '_check_ollama_available', return_value=False):
            client = GraniteClient()
        pipeline = RAGPipeline(granite_client=client)

        assert pipeline.granite is client


class TestDocumentIndexing:
    """Tests for document indexing functionality."""

    def test_index_obd_data(self, rag_pipeline, sample_parsed_data):
        """Test indexing parsed OBD data."""
        chat_id = 1

        rag_pipeline.index_obd_data(sample_parsed_data, chat_id)

        assert chat_id in rag_pipeline._vector_stores
        assert "documents" in rag_pipeline._vector_stores[chat_id]

    def test_index_creates_metric_documents(self, rag_pipeline, sample_parsed_data):
        """Test indexing creates documents for metrics."""
        chat_id = 1

        rag_pipeline.index_obd_data(sample_parsed_data, chat_id)
        docs = rag_pipeline._vector_stores[chat_id]["documents"]

        # Should have documents for metrics, fault codes, and summary
        assert len(docs) >= len(sample_parsed_data["metrics"])

    def test_index_creates_fault_code_documents(self, rag_pipeline, sample_parsed_data):
        """Test indexing creates documents for fault codes."""
        chat_id = 1

        rag_pipeline.index_obd_data(sample_parsed_data, chat_id)
        docs = rag_pipeline._vector_stores[chat_id]["documents"]

        # At least one doc should mention the fault code
        doc_texts = [str(doc) for doc in docs]
        assert any("P0300" in text for text in doc_texts)

    def test_index_empty_data(self, rag_pipeline):
        """Test indexing with empty data."""
        chat_id = 2

        rag_pipeline.index_obd_data({"metrics": [], "fault_codes": [], "statistics": {}}, chat_id)

        # Should still create an entry (with summary document)
        assert chat_id in rag_pipeline._vector_stores

    def test_index_handles_errors_gracefully(self, rag_pipeline):
        """Test indexing handles errors without crashing."""
        chat_id = 3

        # Index with malformed data
        rag_pipeline.index_obd_data(None, chat_id)

        # Should have empty documents
        assert chat_id in rag_pipeline._vector_stores


class TestDocumentCreation:
    """Tests for document creation."""

    def test_create_documents_from_metrics(self, rag_pipeline, sample_parsed_data):
        """Test document creation includes metric information."""
        docs = rag_pipeline._create_documents(sample_parsed_data)

        # Check that metric documents contain expected info
        doc_texts = [str(doc) for doc in docs]
        full_text = " ".join(doc_texts)

        assert "engine_rpm" in full_text.lower() or "rpm" in full_text.lower()
        assert "2500" in full_text

    def test_create_documents_from_fault_codes(self, rag_pipeline, sample_parsed_data):
        """Test document creation includes fault code information."""
        docs = rag_pipeline._create_documents(sample_parsed_data)

        doc_texts = [str(doc) for doc in docs]
        full_text = " ".join(doc_texts)

        assert "P0300" in full_text
        assert "misfire" in full_text.lower()

    def test_create_summary_document(self, rag_pipeline, sample_parsed_data):
        """Test document creation includes summary."""
        docs = rag_pipeline._create_documents(sample_parsed_data)

        doc_texts = [str(doc) for doc in docs]
        full_text = " ".join(doc_texts)

        assert "summary" in full_text.lower()


class TestRetrieval:
    """Tests for document retrieval."""

    def test_retrieve_from_indexed_data(self, rag_pipeline, sample_parsed_data):
        """Test retrieving documents after indexing."""
        chat_id = 1
        rag_pipeline.index_obd_data(sample_parsed_data, chat_id)

        results = rag_pipeline._retrieve("engine rpm", chat_id)

        assert len(results) > 0

    def test_retrieve_nonexistent_chat(self, rag_pipeline):
        """Test retrieving from non-existent chat returns empty."""
        results = rag_pipeline._retrieve("query", 999)

        assert results == []

    def test_retrieve_respects_limit(self, rag_pipeline, sample_parsed_data):
        """Test retrieval respects k limit."""
        chat_id = 1
        rag_pipeline.index_obd_data(sample_parsed_data, chat_id)

        results = rag_pipeline._retrieve("query", chat_id, k=2)

        assert len(results) <= 2


class TestContextBuilding:
    """Tests for context building."""

    def test_build_context_with_metrics(self, rag_pipeline):
        """Test context building includes metrics."""
        context = {
            "metrics": [
                {"name": "engine_rpm", "value": 2500, "unit": "RPM", "status": "normal"}
            ],
            "fault_codes": []
        }

        result = rag_pipeline._build_context(context, [])

        assert "VEHICLE METRICS" in result
        assert "engine_rpm" in result

    def test_build_context_with_fault_codes(self, rag_pipeline):
        """Test context building includes fault codes."""
        context = {
            "metrics": [],
            "fault_codes": [
                {"code": "P0300", "description": "Misfire", "severity": "critical"}
            ]
        }

        result = rag_pipeline._build_context(context, [])

        assert "FAULT CODES" in result
        assert "P0300" in result

    def test_build_context_no_fault_codes(self, rag_pipeline):
        """Test context building with no fault codes."""
        context = {"metrics": [], "fault_codes": []}

        result = rag_pipeline._build_context(context, [])

        assert "None detected" in result

    def test_build_context_with_relevant_docs(self, rag_pipeline):
        """Test context building includes relevant documents."""
        context = {"metrics": [], "fault_codes": []}
        relevant_docs = ["Document 1 content", "Document 2 content"]

        result = rag_pipeline._build_context(context, relevant_docs)

        assert "RELEVANT INFORMATION" in result


class TestPromptSelection:
    """Tests for prompt selection based on query type."""

    def test_select_summary_prompt(self, rag_pipeline):
        """Test summary-related queries use summary prompt."""
        context = {"metrics": [], "fault_codes": []}

        prompt = rag_pipeline._select_prompt("Give me a health summary", context)

        assert "summary" in prompt.lower()

    def test_select_fault_code_prompt(self, rag_pipeline):
        """Test fault code queries use fault code prompt."""
        context = {"metrics": [], "fault_codes": []}

        prompt = rag_pipeline._select_prompt("What is fault code P0300?", context)

        assert "fault" in prompt.lower()

    def test_select_general_prompt(self, rag_pipeline):
        """Test general queries use general prompt."""
        context = {"metrics": [], "fault_codes": []}

        prompt = rag_pipeline._select_prompt("How is my car doing?", context)

        assert "OBD InsightBot" in prompt


class TestQuery:
    """Tests for the query method."""

    def test_query_returns_rag_response(self, rag_pipeline, sample_parsed_data):
        """Test query returns RAGResponse object."""
        chat_id = 1
        rag_pipeline.index_obd_data(sample_parsed_data, chat_id)

        context = {
            "metrics": sample_parsed_data["metrics"],
            "fault_codes": sample_parsed_data["fault_codes"]
        }

        response = rag_pipeline.query("What is my vehicle status?", chat_id, context)

        assert isinstance(response, RAGResponse)
        assert response.response is not None
        assert response.severity in ["critical", "warning", "normal"]

    def test_query_with_critical_fault_codes(self, rag_pipeline, sample_parsed_data):
        """Test query with critical fault codes returns critical severity."""
        chat_id = 1
        rag_pipeline.index_obd_data(sample_parsed_data, chat_id)

        context = {
            "metrics": sample_parsed_data["metrics"],
            "fault_codes": sample_parsed_data["fault_codes"]  # Contains P0300 (critical)
        }

        response = rag_pipeline.query("What are the fault codes?", chat_id, context)

        assert response.severity == "critical"


class TestVehicleSummary:
    """Tests for vehicle summary generation."""

    def test_get_vehicle_summary_healthy(self, rag_pipeline, healthy_parsed_data):
        """Test summary for healthy vehicle."""
        context = {
            "metrics": healthy_parsed_data["metrics"],
            "fault_codes": healthy_parsed_data["fault_codes"]
        }

        response = rag_pipeline.get_vehicle_summary(context)

        assert isinstance(response, RAGResponse)
        assert response.severity == "normal"

    def test_get_vehicle_summary_with_issues(self, rag_pipeline, sample_parsed_data):
        """Test summary for vehicle with issues."""
        context = {
            "metrics": sample_parsed_data["metrics"],
            "fault_codes": sample_parsed_data["fault_codes"]
        }

        response = rag_pipeline.get_vehicle_summary(context)

        assert isinstance(response, RAGResponse)
        assert response.severity == "critical"  # Due to P0300 fault code

    def test_summary_prompt_reflects_status(self, rag_pipeline):
        """Test summary prompt reflects vehicle status."""
        metrics = [{"status": "critical"}]
        fault_codes = []

        prompt = rag_pipeline._get_summary_prompt(metrics, fault_codes, True, False)

        assert "CRITICAL" in prompt


class TestFaultCodeExplanation:
    """Tests for fault code explanation."""

    def test_explain_generic_fault_code(self, rag_pipeline):
        """Test explaining a generic fault code."""
        context = {
            "metrics": [],
            "fault_codes": [{"code": "P0300", "severity": "critical"}]
        }

        response = rag_pipeline.explain_fault_code("P0300", context)

        assert isinstance(response, RAGResponse)
        assert response.severity == "critical"

    def test_explain_manufacturer_specific_code(self, rag_pipeline):
        """Test explaining a manufacturer-specific fault code."""
        context = {
            "metrics": [],
            "fault_codes": [{"code": "P1234", "severity": "warning"}]
        }

        response = rag_pipeline.explain_fault_code("P1234", context)

        assert isinstance(response, RAGResponse)

    def test_fault_code_prompt_for_generic(self, rag_pipeline):
        """Test fault code prompt for generic code."""
        prompt = rag_pipeline._get_fault_code_prompt("P0300", is_generic=True)

        assert "P0300" in prompt
        assert "Generic OBD-II" in prompt

    def test_fault_code_prompt_for_manufacturer_specific(self, rag_pipeline):
        """Test fault code prompt for manufacturer-specific code."""
        prompt = rag_pipeline._get_fault_code_prompt("P1234", is_generic=False)

        assert "P1234" in prompt
        assert "Manufacturer-specific" in prompt


class TestContextFormatting:
    """Tests for context formatting helpers."""

    def test_format_metrics_context(self, rag_pipeline):
        """Test formatting metrics as context string."""
        metrics = [
            {"name": "engine_rpm", "value": 2500, "unit": "RPM", "status": "normal"}
        ]

        result = rag_pipeline._format_metrics_context(metrics)

        assert "VEHICLE METRICS" in result
        assert "engine_rpm" in result
        assert "2500" in result

    def test_format_empty_metrics(self, rag_pipeline):
        """Test formatting empty metrics."""
        result = rag_pipeline._format_metrics_context([])

        assert "No metrics data available" in result

    def test_format_fault_codes_context(self, rag_pipeline):
        """Test formatting fault codes as context string."""
        fault_codes = [
            {"code": "P0300", "description": "Misfire", "severity": "critical"}
        ]

        result = rag_pipeline._format_fault_codes_context(fault_codes)

        assert "FAULT CODES" in result
        assert "P0300" in result
        assert "Misfire" in result

    def test_format_empty_fault_codes(self, rag_pipeline):
        """Test formatting empty fault codes."""
        result = rag_pipeline._format_fault_codes_context([])

        assert "None detected" in result
