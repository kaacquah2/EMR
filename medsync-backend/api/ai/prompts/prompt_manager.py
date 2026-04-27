import os
import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class PromptManager:
    """
    Manages versioned AI prompt templates and enforces clinical sanitization.
    
    Templates are stored in: api/ai/prompts/templates/<agent_name>_v<version>.txt
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
            agent_name: Name of the agent (e.g., 'summary', 'diagnosis')
            version: Semantic version string
            context: Variables to interpolate into the template
            
        Returns:
            Populated prompt string
        """
        file_name = f"{agent_name}_v{version}.txt"
        file_path = os.path.join(self.templates_dir, file_name)
        
        try:
            if not os.path.exists(file_path):
                logger.warning(f"Prompt template not found: {file_path}. Falling back to default.")
                return self._get_fallback_prompt(agent_name, context)
                
            with open(file_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
                
            if context:
                # Sanitize context values
                sanitized_context = {k: self.sanitize_clinical_input(v) for k, v in context.items()}
                return template_content.format(**sanitized_context)
            
            return template_content
            
        except Exception as e:
            logger.error(f"Error loading prompt {agent_name} v{version}: {e}")
            return self._get_fallback_prompt(agent_name, context)

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

    def _get_fallback_prompt(self, agent_name: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Fallback hardcoded prompts if templates are missing."""
        if agent_name == 'summary':
            return f"Summarize clinical findings for patient {context.get('patient_id', 'Unknown')}."
        return f"Process clinical request for agent {agent_name}."

# Singleton instance
_prompt_manager = None

def get_prompt_manager() -> PromptManager:
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager
