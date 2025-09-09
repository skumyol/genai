"""
Output parser utilities for processing LLM responses
"""

import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class OutputParserList:
    """Parse comma-separated list responses"""
    
    @staticmethod
    def parse(response: str) -> List[str]:
        """Parse CSV response into list of strings"""
        try:
            # Clean the response
            response = response.strip()
            # Remove any quotes and split by comma
            items = [item.strip().strip('"\'') for item in response.split(',')]
            # Filter out empty items
            return [item for item in items if item]
        except Exception as e:
            logger.error(f"Error parsing list response: {e}")
            return []

class OutputParserJSON:
    """Parse JSON responses"""
    
    @staticmethod
    def parse(response: str) -> Dict[str, Any]:
        """Parse JSON response into dictionary"""
        try:
            # Try to extract JSON from response
            response = response.strip()
            # Find JSON boundaries if wrapped in text
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            if start_idx != -1 and end_idx != -1:
                json_str = response[start_idx:end_idx+1]
                return json.loads(json_str)
            return json.loads(response)
        except Exception as e:
            logger.error(f"Error parsing JSON response: {e}")
            return {}

# Global instances
output_parser_list = OutputParserList()
output_parser_json = OutputParserJSON()
