from typing import List, Dict, Any
from langchain_core.tools import tool
from src.tools.ticket_tools import classify_and_create_ticket
from src.utils.helpers import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv("call_bot/.env")

@tool
async def save_transcript(transcripts: List[Dict[str, str]]) -> Dict[str, Any]:
    """Save call transcript and create support ticket (async version)

    Args:
        transcripts: List of message dictionaries with 'role', 'text', and 'timestamp'

    Returns:
        Dictionary with operation status and potential error message
    """
    try:
        logger.info(f"Saving call transcript with {len(transcripts)} messages")

        # Validate transcript format
        if not all(
            isinstance(msg, dict) and
            {'role', 'text', 'timestamp'}.issubset(msg.keys())
            for msg in transcripts
        ):
            raise ValueError("Invalid transcript format - missing required fields")

        # Process through ticket system
        result = await classify_and_create_ticket(transcripts)

        if not result or "error" in result:
            raise RuntimeError(f"Ticket creation failed: {result.get('error', 'Unknown error')}")

        return {"status": "success", "ticket_id": result.get("ticket_id")}

    except Exception as e:
        logger.error(f"Transcript save error: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "error_type": e.__class__.__name__
        }
