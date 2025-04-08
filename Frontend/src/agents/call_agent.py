# src/agents/call_agent.py
import asyncio
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.runnables import RunnableLambda
from src.graph.state import CallState
from src.tools.transcript_tools import save_transcript
from src.utils.helpers import ConnectionManager, logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv("call_bot/.env")

class CallAgent:
    def __init__(self, manager: ConnectionManager):
        self.manager = manager
        self.workflow = self.create_workflow()

    def create_workflow(self):
        workflow = StateGraph(CallState)

        # Define workflow nodes
        workflow.add_node("receive_twilio",
            RunnableLambda(self.process_twilio).with_config(name="twilio_input"))
        workflow.add_node("process_ai",
            RunnableLambda(self.process_ai).with_config(name="ai_processing"))
        workflow.add_node("handle_emergency",
            RunnableLambda(self.handle_emergency).with_config(name="emergency_handling"))
        workflow.add_node("save_data",
            ToolNode([save_transcript]).with_config(name="data_saver"))

        # Configure edges
        workflow.add_conditional_edges(
            "receive_twilio",
            self.route_twilio,
            {"process": "process_ai", "emergency": "handle_emergency", "end": "save_data"}
        )

        workflow.add_conditional_edges(
            "process_ai",
            self.route_ai,
            {"continue": "receive_twilio", "emergency": "handle_emergency", "end": "save_data"}
        )

        workflow.add_conditional_edges(
            "handle_emergency",
            self.route_emergency,
            {"continue": "receive_twilio", "end": "save_data"}
        )

        workflow.add_edge("save_data", END)
        workflow.set_entry_point("receive_twilio")

        return workflow.compile()

    async def process_twilio(self, state: CallState) -> CallState:
        try:
            data = await self.manager.twilio_queues[state.client_id].get()
            if data.get('event') == 'media':
                state.transcripts.append({
                    "role": "user",
                    "text": "Audio input",
                    "timestamp": datetime.now().isoformat()
                })
            elif data.get('event') == 'stop':
                state.call_ended = True
        except Exception as e:
            logger.error(f"Twilio processing error: {e}")
        return state

    async def process_ai(self, state: CallState) -> CallState:
        try:
            while True:
                event = await self.manager.openai_queues[state.client_id].get()
                if event.get('type') == 'response.done':
                    content = event['response']['output'][0]['content'][0]['transcript']
                    state.transcripts.append({
                        "role": "assistant",
                        "text": content,
                        "timestamp": datetime.now().isoformat()
                    })
                    await self.manager.active_connections[state.client_id].send_json({
                        "event": "response",
                        "text": content
                    })
                await asyncio.sleep(0.01)
        except Exception as e:
            logger.error(f"AI processing error: {e}")

        return state

    async def handle_emergency(self, state: CallState) -> CallState:
        state.escalated = True
        await self.manager.active_connections[state.client_id].send_json({
            "event": "escalate",
            "message": "Emergency services notified"
        })
        return state

    def route_twilio(self, state: CallState):
        if state.call_ended:
            return "end"
        return "process"

    def route_ai(self, state: CallState):
        if state.escalated:
            return "emergency"
        return "continue"

    def route_emergency(self, state: CallState):
        return "end" if state.call_ended else "continue"

    async def finalize_call(self, state):
        pass