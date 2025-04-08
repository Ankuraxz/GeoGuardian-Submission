# src/register.py
import os
import logging
from flask import Flask, request, jsonify
from uagents_core.identity import Identity
from fetchai.registration import register_with_agentverse
from fetchai.communication import parse_message_from_agent, send_message_to_agent
from src.agents.call_agent import CallAgent
from src.tools.ticket_tools import classify_and_create_ticket
from src.graph.state import CallState
from dotenv import load_dotenv

from utils.helpers import ConnectionManager

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Global agent instances
emergency_identity = None
call_agent = None


def init_emergency_agent():
    """Initialize and register the emergency response agent"""
    global emergency_identity, call_agent
    try:
        # Initialize call agent with connection manager
        call_agent = CallAgent(ConnectionManager())

        # Initialize cryptographic identity
        emergency_identity = Identity.from_seed("EmergencyResponseAgent", 0)

        # Register with Agentverse
        register_with_agentverse(
            identity=emergency_identity,
            url="http://localhost:5008/webhook",
            agentverse_token=os.getenv("AGENTVERSE_API_KEY"),
            agent_title="Emergency Response Coordinator",
            readme="""
                <description>Multi-agency emergency response coordination system</description>
                <capabilities>
                    <capability>Medical emergency triage</capability>
                    <capability>Fire incident coordination</capability>
                    <capability>Crime response dispatch</capability>
                    <capability>Natural disaster management</capability>
                </capabilities>
                <payload_requirements>
                    <emergency_data>
                        <parameter>location</parameter>
                        <parameter>emergency_type</parameter>
                        <parameter>severity</parameter>
                        <parameter>caller_info</parameter>
                    </emergency_data>
                </payload_requirements>
            """
        )
        logger.info("Emergency Response Agent registered successfully!")
    except Exception as e:
        logger.error(f"Agent initialization failed: {e}")
        raise


@app.route('/webhook', methods=['POST'])
async def emergency_webhook():
    """Handle incoming emergency alerts"""
    try:
        data = request.get_data().decode('utf-8')
        message = parse_message_from_agent(data)
        alert_data = message.payload.get("emergency", {})

        # Validate required fields
        required_fields = ['location', 'emergency_type', 'caller_info']
        missing = [field for field in required_fields if field not in alert_data]
        if missing:
            return jsonify({
                "status": "error",
                "message": f"Missing required fields: {missing}"
            }), 400

        # Create initial call state
        state = CallState(
            client_id=message.sender,
            transcripts=[{
                "role": "system",
                "text": f"Emergency alert received: {alert_data}"
            }]
        )

        # Process through emergency workflow
        result = await call_agent.workflow.ainvoke(state)

        # Generate emergency ticket
        ticket = await classify_and_create_ticket(result.transcripts)

        # Format response using module-level helper functions
        response = {
            "status": "dispatched",
            "incident_id": ticket.get("ticket_id"),
            "responders": _determine_responders(alert_data['emergency_type']),
            "actions": _generate_safety_instructions(alert_data)
        }

        # Send confirmation back to the sender
        send_message_to_agent(
            emergency_identity,
            message.sender,
            {'emergency_response': response}
        )
        return jsonify({"status": "response_sent"})

    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


def _determine_responders(emergency_type: str) -> list:
    """Determine appropriate emergency responders"""
    responders = {
        'medical': ["EMS", "Paramedics"],
        'fire': ["Fire Department", "Hazmat"],
        'crime': ["Police", "SWAT"],
        'natural': ["FEMA", "Red Cross"]
    }
    return responders.get(emergency_type.lower(), ["Police", "EMS"])


def _generate_safety_instructions(alert_data: dict) -> list:
    """Generate context-specific safety instructions"""
    instructions = [
        "Stay on the line if safe to do so",
        "Follow operator instructions",
        "Move to a safe location if possible"
    ]

    if alert_data['emergency_type'] == 'fire':
        instructions.append("Do not use elevators")
        instructions.append("Stay low to avoid smoke")

    return instructions


def run_emergency_service():
    """Start the emergency registration service"""
    try:
        init_emergency_agent()
        app.run(host="0.0.0.0", port=5008, debug=False)
    except Exception as e:
        logger.error(f"Service startup failed: {e}")
        raise


if __name__ == "__main__":
    run_emergency_service()