import os
import re
import logging
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger(__name__)

class PromptManager:
    """
    Manages versioned AI prompt templates and enforces clinical sanitization.
    
    Templates are stored in: api/ai/prompts/templates/<agent_name>_v<version>.txt

    Available templates:
    - summary_v1.0.0.txt     — Clinical summary narrative
    - triage_v1.0.0.txt      — ESI-based triage assessment
    - diagnosis_v1.0.0.txt   — Differential diagnosis report
    - risk_report_v1.0.0.txt — Disease risk assessment
    - referral_v1.0.0.txt    — Referral recommendations
    - data_quality_v1.0.0.txt — Data completeness report
    """

    def __init__(self, templates_dir: Optional[str] = None):
        if templates_dir is None:
            # Default to api/ai/prompts/templates/
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.templates_dir = os.path.join(base_dir, 'templates')
        else:
            self.templates_dir = templates_dir
            
        if not os.path.exists(self.templates_dir):
            os.makedirs(self.templates_dir, exist_ok=True)

    def get_prompt(self, agent_name: str, version: str = "1.0.0", context: Optional[Dict[str, Any]] = None) -> str:
        """
        Retrieve and populate a versioned prompt template.
        
        Args:
            agent_name: Name of the agent (e.g., 'summary', 'diagnosis', 'triage')
            version: Semantic version string
            context: Variables to interpolate into the template
            
        Returns:
            Populated prompt string
        """
        file_name = f"{agent_name}_v{version}.txt"
        file_path = os.path.join(self.templates_dir, file_name)
        
        try:
            if not os.path.exists(file_path):
                available = self.list_available_templates()
                agent_templates = [t for t in available if t['agent_name'] == agent_name]
                if agent_templates:
                    latest = agent_templates[-1]
                    logger.warning(
                        f"Template {file_name} not found. "
                        f"Available versions for '{agent_name}': "
                        f"{[t['version'] for t in agent_templates]}. "
                        f"Falling back to v{latest['version']}."
                    )
                    file_path = os.path.join(self.templates_dir, latest['file_name'])
                else:
                    logger.warning(
                        f"No templates found for agent '{agent_name}'. "
                        f"Available agents: {list(set(t['agent_name'] for t in available))}. "
                        f"Using fallback."
                    )
                    return self._get_fallback_prompt(agent_name, context)
                
            with open(file_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
                
            if context:
                # Sanitize context values
                sanitized_context = {k: self.sanitize_clinical_input(v) for k, v in context.items()}
                # Use safe formatting that ignores missing keys
                try:
                    return template_content.format(**sanitized_context)
                except KeyError as e:
                    logger.warning(f"Template variable {e} not in context, using partial format")
                    return self._safe_format(template_content, sanitized_context)
            
            return template_content
            
        except Exception as e:
            logger.error(f"Error loading prompt {agent_name} v{version}: {e}")
            return self._get_fallback_prompt(agent_name, context)

    def list_available_templates(self) -> List[Dict[str, str]]:
        """
        List all available prompt templates.

        Returns:
            List of dicts with 'agent_name', 'version', 'file_name' for each template.
        """
        templates = []
        pattern = re.compile(r'^(.+)_v(\d+\.\d+\.\d+)\.txt$')

        if not os.path.exists(self.templates_dir):
            return templates

        for filename in sorted(os.listdir(self.templates_dir)):
            match = pattern.match(filename)
            if match:
                templates.append({
                    'agent_name': match.group(1),
                    'version': match.group(2),
                    'file_name': filename,
                })

        return templates

    def get_template_version_history(self, agent_name: str) -> List[str]:
        """
        Get all available versions for a given agent template.

        Args:
            agent_name: Name of the agent (e.g., 'summary', 'triage')

        Returns:
            Sorted list of version strings (e.g., ['1.0.0', '1.1.0'])
        """
        templates = self.list_available_templates()
        versions = [t['version'] for t in templates if t['agent_name'] == agent_name]
        return sorted(versions)

    def sanitize_clinical_input(self, value: Any) -> str:
        """
        Sanitize user-provided strings for use in AI prompts.
        - Removes potential PII (basic patterns)
        - Escapes special characters
        - Truncates long strings
        """
        if not isinstance(value, str):
            return str(value)
            
        # 1. Basic PII Redaction (e.g., Phone numbers, Email - simplistic for demo)
        # Phone numbers (GH format)
        value = re.sub(r'\+?233\s?\d{2,3}\s?\d{3}\s?\d{4}', '[PHONE]', value)
        # Email
        value = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[EMAIL]', value)
        
        # 2. Prevent Prompt Injection (Remove common escape patterns)
        value = value.replace('{', '(').replace('}', ')')
        
        # 3. Truncate (Prevent context window overflow/abuse)
        MAX_LEN = 2000
        if len(value) > MAX_LEN:
            value = value[:MAX_LEN] + "..."
            
        return value.strip()

    def _safe_format(self, template: str, context: Dict[str, str]) -> str:
        """Format template, leaving unknown placeholders as-is."""
        result = template
        for key, value in context.items():
            result = result.replace('{' + key + '}', str(value))
        return result

    def _get_fallback_prompt(self, agent_name: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Fallback hardcoded prompts if templates are missing."""
        ctx = context or {}
        if agent_name == 'summary':
            return f"Summarize clinical findings for patient {ctx.get('patient_id', 'Unknown')}."
        elif agent_name == 'triage':
            return f"Triage assessment for patient {ctx.get('patient_id', 'Unknown')}."
        elif agent_name == 'diagnosis':
            return f"Differential diagnosis for patient {ctx.get('patient_id', 'Unknown')}."
        elif agent_name == 'risk_report':
            return f"Risk report for patient {ctx.get('patient_id', 'Unknown')}."
        elif agent_name == 'referral':
            return f"Referral recommendation for patient {ctx.get('patient_id', 'Unknown')}."
        elif agent_name == 'data_quality':
            return f"Data quality assessment for patient {ctx.get('patient_id', 'Unknown')}."
        return f"Process clinical request for agent {agent_name}."

# Singleton instance
_prompt_manager = None

def get_prompt_manager() -> PromptManager:
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager

