"""
Prompt templates for IBM Granite interactions.
"""


class PromptTemplates:
    """Collection of prompt templates for different query types."""

    SYSTEM_PROMPT = """You are OBD InsightBot, a friendly and knowledgeable automotive diagnostic assistant.

Your role is to help users understand their vehicle's OBD-II diagnostic data in simple, non-technical language.

Guidelines:
1. Always explain technical terms in simple language that anyone can understand
2. Be clear about the severity of any issues (critical, warning, or normal)
3. Provide practical recommendations when issues are detected
4. If you don't have information about something, say so clearly
5. Prioritize safety - always recommend professional inspection for serious issues
6. Be conversational and supportive, as users may be worried about their vehicle

Response Severity Levels:
- CRITICAL (Red): Immediate attention required - stop driving
- WARNING (Amber): Should be addressed soon
- NORMAL (Green): No immediate concern"""

    VEHICLE_SUMMARY = """Analyze the following OBD-II diagnostic data and provide a comprehensive vehicle health summary.

VEHICLE METRICS:
{metrics}

FAULT CODES:
{fault_codes}

Please provide:
1. **Overall Health Status** - Is the vehicle healthy, needs attention, or has critical issues?
2. **Key Findings** - List the most important observations
3. **Detailed Analysis** - Explain any concerning readings
4. **Recommendations** - What actions should the owner take?

Use simple, non-technical language. Be supportive but honest about any issues."""

    FAULT_CODE_EXPLANATION = """Explain the following OBD-II fault code to a vehicle owner who is not a mechanic.

FAULT CODE: {fault_code}
CODE TYPE: {code_type}
DESCRIPTION: {description}
SEVERITY: {severity}

Please explain:
1. **What This Code Means** - In simple terms
2. **Common Causes** - List 3-5 most likely causes
3. **Symptoms** - What might the driver notice?
4. **Urgency** - Can they keep driving or should they stop?
5. **Recommended Actions** - What should they do next?

Be reassuring but prioritize safety."""

    METRIC_ANALYSIS = """Analyze the following vehicle metric reading and explain it to the user.

METRIC: {metric_name}
CURRENT VALUE: {value} {unit}
NORMAL RANGE: {normal_range}
STATUS: {status}

Please explain:
1. What this metric measures and why it matters
2. Whether the current reading is concerning
3. What might cause abnormal readings
4. Any recommended actions

Use simple language and be supportive."""

    FOLLOW_UP_QUESTION = """The user has a follow-up question about their vehicle's diagnostics.

PREVIOUS CONTEXT:
{previous_context}

USER'S QUESTION:
{question}

Provide a helpful response that:
1. Directly answers their question
2. References relevant information from the diagnostic data
3. Suggests additional questions they might want to ask
4. Maintains a supportive, conversational tone"""

    NO_DATA_RESPONSE = """The user is asking about something not covered in their OBD-II diagnostic data.

USER'S QUESTION: {question}

AVAILABLE DATA TYPES:
{available_data}

Please:
1. Explain that this specific information is not available in the OBD-II data
2. Describe what the OBD-II system does and doesn't monitor
3. Suggest how they might get this information (e.g., visual inspection, dealer visit)
4. Offer to help with any other questions about the available data"""

    NO_FAULT_CODES = """The user is asking about fault codes, but none were found in their data.

Please explain:
1. That no fault codes (DTCs) were detected
2. What this means (good news!)
3. That lack of codes doesn't guarantee everything is perfect
4. Recommend regular maintenance regardless
5. Suggest what types of issues would trigger fault codes"""

    @classmethod
    def format_vehicle_summary(cls, metrics: list, fault_codes: list) -> str:
        """Format the vehicle summary prompt with data."""
        metrics_str = "\n".join([
            f"- {m.get('name', 'Unknown')}: {m.get('value', 'N/A')} {m.get('unit', '')} "
            f"(Status: {m.get('status', 'unknown')})"
            for m in metrics
        ]) if metrics else "No metrics data available"

        fault_str = "\n".join([
            f"- {f.get('code', 'Unknown')}: {f.get('description', 'No description')} "
            f"(Severity: {f.get('severity', 'unknown')})"
            for f in fault_codes
        ]) if fault_codes else "No fault codes detected"

        return cls.VEHICLE_SUMMARY.format(
            metrics=metrics_str,
            fault_codes=fault_str
        )

    @classmethod
    def format_fault_code_explanation(
        cls,
        code: str,
        code_type: str = "Generic",
        description: str = "",
        severity: str = "warning"
    ) -> str:
        """Format the fault code explanation prompt."""
        return cls.FAULT_CODE_EXPLANATION.format(
            fault_code=code,
            code_type=code_type,
            description=description,
            severity=severity
        )

    @classmethod
    def format_metric_analysis(
        cls,
        metric_name: str,
        value: float,
        unit: str,
        normal_range: str,
        status: str
    ) -> str:
        """Format the metric analysis prompt."""
        return cls.METRIC_ANALYSIS.format(
            metric_name=metric_name,
            value=value,
            unit=unit,
            normal_range=normal_range,
            status=status
        )
