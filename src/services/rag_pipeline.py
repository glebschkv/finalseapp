"""
RAG (Retrieval-Augmented Generation) Pipeline for OBD InsightBot.
Implements BR4: General Vehicle Status Queries and BR5: Fault Code Explanation
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from ..config.settings import get_settings
from ..config.logging_config import get_logger
from .granite_client import GraniteClient
from .severity_classifier import SeverityClassifier

logger = get_logger(__name__)

# Try to import vector store libraries
try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_community.vectorstores import Chroma
    from langchain.schema import Document
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False
    logger.warning("LangChain not fully installed. Using simplified RAG.")


@dataclass
class RAGResponse:
    """Response from the RAG pipeline."""
    response: str
    severity: str
    sources: List[Dict[str, Any]]
    confidence: float = 1.0


class RAGPipeline:
    """
    RAG Pipeline for OBD-II diagnostic queries.

    Implements:
    - BR4.1: Summary when all metrics normal
    - BR4.2: Summary when metrics are abnormal
    - BR4.3: Query about unavailable data
    - BR5.1: Specific fault code explanation
    - BR5.2: Summary of all fault codes
    - BR5.3: Manufacturer-specific fault code handling
    - BR5.4: Query when no fault codes exist
    """

    def __init__(self, granite_client: Optional[GraniteClient] = None):
        """
        Initialize the RAG pipeline.

        Args:
            granite_client: Optional pre-configured Granite client
        """
        self.granite = granite_client or GraniteClient()
        self.severity_classifier = SeverityClassifier()
        self.settings = get_settings()

        # Vector store per chat
        self._vector_stores: Dict[int, Any] = {}

        # Text splitter for chunking
        if HAS_LANGCHAIN:
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=500,
                chunk_overlap=50,
                separators=["\n\n", "\n", ". ", " ", ""]
            )

    def index_obd_data(self, parsed_data: Dict[str, Any], chat_id: int) -> None:
        """
        Index parsed OBD-II data into the vector store.

        Args:
            parsed_data: Parsed OBD-II data from OBDParser
            chat_id: Chat ID for storage
        """
        try:
            documents = self._create_documents(parsed_data)

            if not documents:
                logger.warning(f"No documents to index for chat {chat_id}")
                return

            # Store documents directly for simple retrieval (most reliable approach)
            # Vector store with embeddings is optional and can fail
            self._vector_stores[chat_id] = {"documents": documents}
            logger.info(f"Indexed {len(documents)} documents for chat {chat_id}")

        except Exception as e:
            logger.error(f"Failed to index OBD data for chat {chat_id}: {e}")
            # Ensure we have at least an empty store to prevent crashes
            self._vector_stores[chat_id] = {"documents": []}

    def query(self, user_query: str, chat_id: int, chat_context: Dict[str, Any]) -> RAGResponse:
        """
        Process a user query through the RAG pipeline.

        Args:
            user_query: User's question
            chat_id: Chat ID for context retrieval
            chat_context: Additional context (parsed_metrics, fault_codes)

        Returns:
            RAGResponse with answer, severity, and sources
        """
        # Retrieve relevant context
        relevant_docs = self._retrieve(user_query, chat_id)

        # Build augmented context
        context = self._build_context(chat_context, relevant_docs)

        # Determine query type and select appropriate prompt
        prompt = self._select_prompt(user_query, chat_context)

        # Generate response
        response = self.granite.generate_response(
            prompt=user_query,
            context=context,
            system_prompt=prompt
        )

        # Classify severity
        severity = self.severity_classifier.classify(
            response=response,
            metrics=chat_context.get("metrics", []),
            fault_codes=chat_context.get("fault_codes", [])
        )

        return RAGResponse(
            response=response,
            severity=severity,
            sources=[{"content": doc} for doc in relevant_docs[:3]]
        )

    def get_vehicle_summary(self, chat_context: Dict[str, Any]) -> RAGResponse:
        """
        Generate a comprehensive vehicle health summary (BR4.1, BR4.2).

        Args:
            chat_context: Parsed metrics and fault codes

        Returns:
            RAGResponse with summary
        """
        metrics = chat_context.get("metrics", [])
        fault_codes = chat_context.get("fault_codes", [])

        # Determine overall status
        has_critical = any(m.get("status") == "critical" for m in metrics)
        has_critical = has_critical or any(f.get("severity") == "critical" for f in fault_codes)

        has_warning = any(m.get("status") == "warning" for m in metrics)
        has_warning = has_warning or any(f.get("severity") == "warning" for f in fault_codes)

        # Build summary prompt
        prompt = self._get_summary_prompt(metrics, fault_codes, has_critical, has_warning)

        context = self._format_metrics_context(metrics) + "\n\n" + self._format_fault_codes_context(fault_codes)

        response = self.granite.generate_response(
            prompt="Provide a complete vehicle health summary.",
            context=context,
            system_prompt=prompt
        )

        severity = "critical" if has_critical else ("warning" if has_warning else "normal")

        return RAGResponse(
            response=response,
            severity=severity,
            sources=[]
        )

    def explain_fault_code(self, code: str, chat_context: Dict[str, Any]) -> RAGResponse:
        """
        Explain a specific fault code (BR5.1, BR5.3).

        Args:
            code: Fault code to explain (e.g., "P0300")
            chat_context: Additional context

        Returns:
            RAGResponse with explanation
        """
        # Check if it's a manufacturer-specific code
        is_generic = code[1] in ["0", "2", "3"] if len(code) > 1 else True

        prompt = self._get_fault_code_prompt(code, is_generic)

        response = self.granite.generate_response(
            prompt=f"Explain the fault code {code}",
            context=f"Fault Code: {code}\nType: {'Generic OBD-II' if is_generic else 'Manufacturer-specific'}",
            system_prompt=prompt
        )

        # Determine severity from fault code
        severity = "warning"
        for fc in chat_context.get("fault_codes", []):
            if fc.get("code") == code:
                severity = fc.get("severity", "warning")
                break

        return RAGResponse(
            response=response,
            severity=severity,
            sources=[]
        )

    def _create_documents(self, parsed_data: Dict[str, Any]) -> List[Any]:
        """Create document chunks from parsed OBD data."""
        documents = []

        # Create metric documents
        for metric in parsed_data.get("metrics", []):
            doc_text = f"""
Metric: {metric.get('name', 'Unknown')}
Value: {metric.get('value', 'N/A')} {metric.get('unit', '')}
Status: {metric.get('status', 'unknown')}
Normal Range: {metric.get('normal_range', 'N/A')}
Description: {metric.get('description', '')}
"""
            if HAS_LANGCHAIN:
                documents.append(Document(
                    page_content=doc_text,
                    metadata={"type": "metric", "name": metric.get("name")}
                ))
            else:
                documents.append(doc_text)

        # Create fault code documents
        for fault in parsed_data.get("fault_codes", []):
            doc_text = f"""
Fault Code: {fault.get('code', 'Unknown')}
Description: {fault.get('description', 'No description')}
Severity: {fault.get('severity', 'unknown')}
Category: {fault.get('category', 'unknown')}
Possible Causes: {', '.join(fault.get('possible_causes', []))}
Recommended Action: {fault.get('recommended_action', 'Consult a mechanic')}
"""
            if HAS_LANGCHAIN:
                documents.append(Document(
                    page_content=doc_text,
                    metadata={"type": "fault_code", "code": fault.get("code")}
                ))
            else:
                documents.append(doc_text)

        # Create summary document
        stats = parsed_data.get("statistics", {})
        summary_text = f"""
Vehicle Diagnostic Summary:
Total Metrics Analyzed: {stats.get('metrics_count', 0)}
Normal Readings: {stats.get('normal_count', 0)}
Warning Readings: {stats.get('warning_count', 0)}
Critical Readings: {stats.get('critical_count', 0)}
Total Data Points: {stats.get('total_rows', 0)}
"""
        if HAS_LANGCHAIN:
            documents.append(Document(
                page_content=summary_text,
                metadata={"type": "summary"}
            ))
        else:
            documents.append(summary_text)

        return documents

    def _retrieve(self, query: str, chat_id: int, k: int = 5) -> List[str]:
        """Retrieve relevant documents for a query."""
        store = self._vector_stores.get(chat_id)
        if not store:
            return []

        if isinstance(store, dict):
            # Simple document storage - return all
            docs = store.get("documents", [])
            if HAS_LANGCHAIN:
                return [doc.page_content if hasattr(doc, 'page_content') else str(doc) for doc in docs[:k]]
            return docs[:k]

        try:
            # Vector store similarity search
            results = store.similarity_search(query, k=k)
            return [doc.page_content for doc in results]
        except Exception as e:
            logger.error(f"Retrieval error: {e}")
            return []

    def _build_context(self, chat_context: Dict[str, Any], relevant_docs: List[str]) -> str:
        """Build the full context string for generation."""
        parts = []

        # Add metrics summary
        metrics = chat_context.get("metrics", [])
        if metrics:
            parts.append("VEHICLE METRICS:")
            for m in metrics:
                status_icon = {"critical": "🔴", "warning": "🟡", "normal": "🟢"}.get(m.get("status"), "⚪")
                parts.append(f"  {status_icon} {m.get('name')}: {m.get('value')} {m.get('unit')} ({m.get('status')})")

        # Add fault codes
        fault_codes = chat_context.get("fault_codes", [])
        if fault_codes:
            parts.append("\nFAULT CODES:")
            for f in fault_codes:
                parts.append(f"  - {f.get('code')}: {f.get('description')} [{f.get('severity')}]")
        else:
            parts.append("\nFAULT CODES: None detected")

        # Add retrieved context
        if relevant_docs:
            parts.append("\nRELEVANT INFORMATION:")
            for doc in relevant_docs[:3]:
                parts.append(f"  {doc[:200]}...")

        return "\n".join(parts)

    def _select_prompt(self, query: str, context: Dict[str, Any]) -> str:
        """Select the appropriate system prompt based on query type."""
        query_lower = query.lower()

        if any(word in query_lower for word in ["summary", "health", "status", "overview"]):
            return self._get_summary_system_prompt()
        elif any(word in query_lower for word in ["fault", "code", "error", "dtc", "p0", "p1", "p2"]):
            return self._get_fault_code_system_prompt()
        else:
            return self._get_general_system_prompt()

    def _get_summary_system_prompt(self) -> str:
        """Get system prompt for vehicle summaries."""
        return """You are OBD InsightBot, an expert automotive diagnostic assistant.

You are providing a vehicle health summary. Follow these guidelines:

1. Start with an overall health status (Healthy, Needs Attention, or Critical)
2. List any critical issues first, then warnings, then normal readings
3. Explain technical terms in simple language
4. Provide specific, actionable recommendations
5. If all metrics are normal, reassure the user but remind them of regular maintenance

Format your response clearly with sections for:
- Overall Status
- Key Findings
- Recommendations

Be conversational but professional. Remember the user may not be technically savvy."""

    def _get_fault_code_system_prompt(self) -> str:
        """Get system prompt for fault code explanations."""
        return """You are OBD InsightBot, an expert automotive diagnostic assistant.

You are explaining OBD-II fault codes. Follow these guidelines:

1. Start with what the code means in simple terms
2. Explain possible causes (most common first)
3. Describe symptoms the driver might notice
4. Provide urgency level (can they keep driving or should they stop?)
5. Give recommendations for next steps

For manufacturer-specific codes (second digit is 1), explain that:
- These are specific to the vehicle manufacturer
- A dealer or specialized mechanic may be needed
- Generic scan tools might not provide full details

Always prioritize safety in your recommendations."""

    def _get_general_system_prompt(self) -> str:
        """Get system prompt for general queries."""
        return """You are OBD InsightBot, a friendly and knowledgeable automotive diagnostic assistant.

Guidelines for responding:
1. Answer based on the OBD-II data provided in the context
2. If asked about something not in the data, clearly state that
3. Use simple, non-technical language
4. Be helpful and supportive
5. Recommend professional inspection when appropriate

If you cannot find information about what the user is asking:
- Clearly state that the information is not available in the uploaded data
- Explain what types of data the OBD-II system does and doesn't monitor
- Suggest how they might get that information"""

    def _get_summary_prompt(self, metrics: List, fault_codes: List, has_critical: bool, has_warning: bool) -> str:
        """Get prompt for summary generation."""
        if has_critical:
            status = "CRITICAL - Immediate attention required"
        elif has_warning:
            status = "WARNING - Some issues need attention"
        else:
            status = "HEALTHY - No significant issues detected"

        return f"""Generate a vehicle health summary.

Overall Status: {status}
Metrics Analyzed: {len(metrics)}
Fault Codes Found: {len(fault_codes)}

Provide a clear, user-friendly summary that:
1. States the overall vehicle health status
2. Highlights any concerning readings
3. Explains fault codes if present
4. Gives practical recommendations
5. Reassures the user where appropriate"""

    def _get_fault_code_prompt(self, code: str, is_generic: bool) -> str:
        """Get prompt for fault code explanation."""
        code_type = "Generic OBD-II" if is_generic else "Manufacturer-specific"

        return f"""Explain the OBD-II fault code {code}.

Code Type: {code_type}

Provide:
1. Clear explanation of what this code means
2. Common causes (list 3-5)
3. Symptoms the driver might experience
4. Severity/urgency level
5. Recommended actions

{"Note: This is a manufacturer-specific code. Recommend consulting a dealer or specialist for precise diagnosis." if not is_generic else ""}"""

    def _format_metrics_context(self, metrics: List[Dict]) -> str:
        """Format metrics as context string."""
        if not metrics:
            return "No metrics data available."

        lines = ["VEHICLE METRICS:"]
        for m in metrics:
            lines.append(f"- {m.get('name')}: {m.get('value')} {m.get('unit')} (Status: {m.get('status')})")
        return "\n".join(lines)

    def _format_fault_codes_context(self, fault_codes: List[Dict]) -> str:
        """Format fault codes as context string."""
        if not fault_codes:
            return "FAULT CODES: None detected"

        lines = ["FAULT CODES:"]
        for f in fault_codes:
            lines.append(f"- {f.get('code')}: {f.get('description')} (Severity: {f.get('severity')})")
        return "\n".join(lines)
