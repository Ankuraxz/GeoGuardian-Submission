# src/tools/ticket_tools.py
import json
import logging
import uuid
import datetime
from typing import Optional, Dict, Any, List
from langgraph.graph import StateGraph, END
from openai import AsyncOpenAI
from src.graph.state import TicketState
from dotenv import load_dotenv

# Load environment variables
load_dotenv("/Users/ankur/genesisAIHackathon/call_bot/.env")

logger = logging.getLogger(__name__)
client = AsyncOpenAI()


class TicketAgents:
    @staticmethod
    async def generate_classification(state: TicketState) -> TicketState:
        """Agent: Generate classification using GPT-4"""
        try:
            completion = await client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": f"Based on transcript: {json.dumps(state.transcripts)}\n\nProduce JSON with: name, priority (high/medium/low), summary, services_needed, life_threatening (bool), ticket_type (medical/fire/crime), location, affected_people (int), suspect_description (if crime). Return only JSON."
                }]
            )
            return TicketState(
                **state.dict(),
                completion=completion.choices[0].message.content,
                error=None
            )
        except Exception as e:
            logger.error(f"Classification error: {str(e)}", exc_info=True)
            return TicketState(
                **state.dict(),
                error={"message": str(e), "type": e.__class__.__name__}
            )

    @staticmethod
    async def parse_response(state: TicketState) -> TicketState:
        """Agent: Parse and clean JSON response"""
        if state.error:
            return state

        try:
            cleaned = state.completion.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(cleaned)
            return TicketState(
                **state.dict(),
                parsed_response=TicketAgents._add_metadata(parsed),
                error=None
            )
        except Exception as e:
            logger.error(f"Parsing error: {str(e)}", exc_info=True)
            return TicketState(
                **state.dict(),
                error={"message": str(e), "type": e.__class__.__name__}
            )

    @staticmethod
    def _add_metadata(response: Dict) -> Dict:
        """Add system-generated metadata to response"""
        return {
            **response,
            "ticket_id": f"TICKET-{uuid.uuid4().hex[:8].upper()}",
            "received_at": datetime.datetime.now().isoformat(),
            "severity_score": {"high": 3, "medium": 2, "low": 1}.get(
                response.get("priority", "").lower(), 0
            )
        }

    @staticmethod
    async def handle_error(state: TicketState) -> TicketState:
        """Agent: Error handling and recovery"""
        if state.error:
            logger.error(f"Processing error: {state.error['message']}")
            return TicketState(
                **state.dict(),
                parsed_response={
                    "error": state.error["message"],
                    "error_type": state.error["type"],
                    "status": "failed"
                },
                status="failed"
            )
        return state


class TicketTools:
    @staticmethod
    async def firebase_upload(state: TicketState) -> TicketState:
        """Tool: Handle Firebase upload with validation"""
        if state.error or not state.parsed_response:
            return state

        try:
            response = state.parsed_response
            required_fields = ['priority', 'location', 'ticket_type']
            missing = [field for field in required_fields if field not in response]

            if missing:
                raise ValueError(f"Missing required fields: {', '.join(missing)}")

            # Uncomment when Firebase configured
            # doc_ref = db.collection('tickets').document(response['ticket_id'])
            # doc_ref.set(response)

            logger.info(f"Created ticket {response['ticket_id']}")
            return TicketState(
                **state.dict(),
                status="uploaded"
            )

        except Exception as e:
            logger.error(f"Upload error: {str(e)}", exc_info=True)
            return TicketState(
                **state.dict(),
                error={"message": str(e), "type": e.__class__.__name__}
            )


def create_ticket_workflow():
    """Create async-compatible LangGraph workflow"""
    workflow = StateGraph(TicketState)

    workflow.add_node("generate", TicketAgents.generate_classification)
    workflow.add_node("parse", TicketAgents.parse_response)
    workflow.add_node("upload", TicketTools.firebase_upload)
    workflow.add_node("handle_errors", TicketAgents.handle_error)

    workflow.set_entry_point("generate")

    workflow.add_conditional_edges(
        "generate",
        lambda s: "handle_errors" if s.error else "parse"
    )
    workflow.add_conditional_edges(
        "parse",
        lambda s: "handle_errors" if s.error else "upload"
    )
    workflow.add_conditional_edges(
        "upload",
        lambda s: "handle_errors" if s.error else END
    )
    workflow.add_edge("handle_errors", END)

    return workflow.compile()


ticket_workflow = create_ticket_workflow()


async def classify_and_create_ticket(transcripts: List[Dict]) -> Dict:
    """Async entry point for ticket processing"""
    try:
        logger.info(f"Processing transcript with {len(transcripts)} messages")
        initial_state = TicketState(
            transcripts=transcripts,
            status="pending"
        )
        result = await ticket_workflow.ainvoke(initial_state)
        return result.parsed_response or {"status": "unknown_error"}

    except Exception as e:
        logger.error(f"Classification failed: {str(e)}", exc_info=True)
        return {
            "error": str(e),
            "error_type": e.__class__.__name__,
            "status": "system_error"
        }