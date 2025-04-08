# main.py
import json
import os
import asyncio
import websockets
from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse
from fastapi.websockets import WebSocketDisconnect
from twilio.twiml.voice_response import VoiceResponse, Connect
from dotenv import load_dotenv

from src.utils.helpers import ConnectionManager, logger
from src.agents.call_agent import CallAgent

# Initialize environment and core components
load_dotenv()
app = FastAPI()
manager = ConnectionManager()
call_agent = CallAgent(manager)

# Environment variables
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
PORT = int(os.getenv('PORT', 5050))
SYSTEM_PROMPT = os.getenv('SYSTEM_PROMPT', 'Emergency response protocol v2.1')


@app.on_event("startup")
async def startup_event():
    """Initialize background tasks"""
    asyncio.create_task(manager.monitor_queues())
    asyncio.create_task(manager.process_media_packets())
    asyncio.create_task(manager.check_websocket_health())


@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """Main WebSocket endpoint for media stream processing"""
    client_id = str(id(websocket))
    keepalive_task = None

    async def send_keepalive():
        while True:
            await websocket.send_json({"event": "keepalive"})
            await asyncio.sleep(15)
    try:
        await websocket.accept()
        logger.info(f"Client connected: {client_id}")
        keepalive_task = asyncio.create_task(send_keepalive())

        await manager.connect(websocket, client_id)
        await websocket.send_json({
            "event": "connected",
            "protocolVersion": "1.0",
            "parameters": {
                "name": "EmergencyAI",
                "track": "both_tracks"
            }
        })

        async with websockets.connect(
                'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview',
                extra_headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "OpenAI-Beta": "realtime=v1"
                }
        ) as openai_ws:
            await initialize_openai_session(openai_ws)
            await process_client_stream(client_id, openai_ws)
    except WebSocketDisconnect:
        logger.warning(f"Client disconnected: {client_id}")
    except Exception as e:
        logger.error(f"Connection error: {client_id} - {str(e)}")
    finally:
        if keepalive_task:
            keepalive_task.cancel()
        await cleanup_client(client_id)


async def initialize_openai_session(ws):
    """Initialize OpenAI real-time session"""
    await ws.send(json.dumps({
        "type": "session.update",
        "session": {
            "turn_detection": {"type": "server_vad"},
            "input_audio_format": "g711_ulaw",
            "output_audio_format": "g711_ulaw",
            "voice": 'alloy',
            "instructions": SYSTEM_PROMPT,
            "modalities": ["text", "audio"],
            "temperature": 0.8,
            "model": "gpt-4o-realtime-preview",
            "max_response_output_tokens": "inf",
        }
    }))
    # Add initial conversation prompt
    await ws.send(json.dumps({
        "type": "conversation.item.create",
        "item": {
            "type": "message",
            "role": "user",
            "content": [{
                "type": "input_text",
                "text": "Greet the user with 'Hello! This is emergency services. What is your emergency?'"
            }]
        }
    }))
    await ws.send(json.dumps({"type": "response.create"}))


async def forward_twilio_media(client_id: str, openai_ws: websockets.WebSocketClientProtocol):
    try:
        while True:
            message = await manager.get_twilio_event(client_id)
            if message and message.get('event') == 'media':
                await openai_ws.send(json.dumps({
                    "type": "input_audio_buffer.append",
                    "audio": message['media']['payload']
                }))
            await asyncio.sleep(0.01)
    except Exception as e:
        logger.error(f"Media forwarding error: {str(e)}")

async def process_client_stream(client_id: str, openai_ws):
    """Process client media stream"""
    # Update the tasks list in process_client_stream
    tasks = [
        asyncio.create_task(forward_twilio_media(client_id, openai_ws)),
        asyncio.create_task(handle_openai_messages(client_id, openai_ws)),
        asyncio.create_task(run_agent_workflow(client_id))
    ]
    await asyncio.gather(*tasks)


async def handle_twilio_messages(client_id: str):
    """Process incoming Twilio media packets"""
    try:
        while True:
            message = await manager.get_twilio_event(client_id)
            if not message:
                await asyncio.sleep(0.1)
                continue

            if message.get('event') == 'media':
                await manager.process_media_packet(client_id, message)

    except Exception as e:
        logger.error(f"Twilio processing failed: {client_id} - {str(e)}")


async def handle_openai_messages(client_id: str, ws):
    """Process OpenAI real-time responses"""
    try:
        async for message in ws:
            event = json.loads(message)
            await manager.handle_openai_event(client_id, event)
    except Exception as e:
        logger.error(f"OpenAI processing failed: {client_id} - {str(e)}")


async def run_agent_workflow(client_id: str):
    """Execute LangGraph workflow for call processing"""
    try:
        async for _ in call_agent.workflow.astream(manager.states[client_id]):
            await manager.handle_state_updates(client_id)
    except Exception as e:
        logger.error(f"Workflow failed: {client_id} - {str(e)}")


async def cleanup_client(client_id: str):
    """Cleanup client resources"""
    try:
        state = manager.states.get(client_id)
        if state:
            await call_agent.finalize_call(state)
            await manager.disconnect(client_id)
            logger.info(f"Cleanup complete: {client_id}")
    except Exception as e:
        logger.error(f"Cleanup error: {client_id} - {str(e)}")


@app.get("/", response_class=HTMLResponse)
async def index_page():
    return """<html>
        <body>
            <h1>Emergency Response System</h1>
            <p>Operational Status: <span style="color: green;">●</span> Online</p>
        </body>
    </html>"""


@app.post("/incoming-call")
async def handle_incoming_call(request: Request):
    """Handle Twilio voice call webhook"""
    response = VoiceResponse()
    try:
        # Use absolute URL with ngrok/domain for local development

        ws_url = f"wss://{request.headers.get('host')}/media-stream"
        print(f"Connecting to {ws_url}")

        connect = Connect().stream(
            url=ws_url,
            name="EmergencyAI",
            track="both_tracks"
        )
        response.append(connect)
        response.pause(length=3)  # Give time for WebSocket connection

        logger.info(f"Using WebSocket URL: {ws_url}")
        return HTMLResponse(content=str(response), media_type="application/xml")
    except Exception as e:
        logger.error(f"Twilio call handling error: {str(e)}")
        return HTMLResponse(content="Error processing call", status_code=500)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)