"""
Multi-Agent Orchestrator - Coordinates 7 AI agents for complete patient analysis.

Agents:
- Data Agent: Validate/clean EMR data
- Prediction Agent: Disease risk scoring
- Diagnosis Agent: Differential diagnosis
- Triage Agent: Urgency assessment
- Similarity Agent: Find similar cases
- Referral Agent: Hospital recommendations
- Summary Agent: Synthesize all outputs
"""

from .orchestrator import AIOrchestrator, get_orchestrator

__all__ = [
    'AIOrchestrator',
    'get_orchestrator',
]
