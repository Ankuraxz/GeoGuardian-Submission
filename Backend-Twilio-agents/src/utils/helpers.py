# src/utils/helpers.py
import os
import asyncio
import logging
import json
from typing import Dict, Any, Optional
from fastapi.websockets import WebSocket
from datetime import datetime
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def configure_logging():
    """Configure structured logging"""
    return logger


def load_environment():
    """Load and validate environment variables"""
    load_dotenv()
    required_vars = ['OPENAI_API_KEY', 'TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN']
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")
    return {
        'openai_key': os.getenv('OPENAI_API_KEY'),
        'twilio_sid': os.getenv('TWILIO_ACCOUNT_SID'),
        'twilio_token': os.getenv('TWILIO_AUTH_TOKEN')
    }


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.twilio_queues: Dict[str, asyncio.Queue] = {}
        self.openai_queues: Dict[str, asyncio.Queue] = {}
        self.interruption_events: Dict[str, asyncio.Event] = {}
        self.states: Dict[str, Any] = {}
        self.stream_sids = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        """Register new connection with initial state"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.twilio_queues[client_id] = asyncio.Queue(maxsize=100)
        self.openai_queues[client_id] = asyncio.Queue(maxsize=100)
        self.states[client_id] = {
            'connected_at': datetime.now(),
            'last_activity': datetime.now(),
            'media_counter': 0,
            'call_status': 'connecting'
        }
        logger.info(f"Client {client_id} connected")

    def disconnect(self, client_id: str):
        """Cleanup client resources"""
        for collection in [self.active_connections,
                           self.twilio_queues,
                           self.openai_queues,
                           self.interruption_events,
                           self.states]:
            collection.pop(client_id, None)
        logger.info(f"Client {client_id} resources cleaned up")

    async def monitor_queues(self):
        """Background task to monitor queue health"""
        while True:
            await asyncio.sleep(5)
            for client_id in list(self.active_connections.keys()):
                twilio_qsize = self.twilio_queues[client_id].qsize()
                openai_qsize = self.openai_queues[client_id].qsize()

                if twilio_qsize > 50:
                    logger.warning(f"Client {client_id} Twilio queue backlog: {twilio_qsize}")
                if openai_qsize > 50:
                    logger.warning(f"Client {client_id} OpenAI queue backlog: {openai_qsize}")

    async def process_media_packets(self):
        """Process media packets from Twilio"""
        while True:
            await asyncio.sleep(0.1)  # Prevent CPU saturation
            for client_id in list(self.twilio_queues.keys()):
                try:
                    message = await self.twilio_queues[client_id].get()
                    await self.process_media_packet(client_id, message)
                except asyncio.QueueEmpty:
                    continue
                except Exception as e:
                    logger.error(f"Media processing error for {client_id}: {str(e)}")

    async def process_media_packet(self, client_id: str, message: Dict):
        """Handle individual media packet"""
        try:
            if message['event'] == 'start':
                await self.handle_twilio_start(client_id, message['start']['streamSid'])
                return

            if message['event'] == 'media' and 'payload' in message['media']:
                await self.openai_queues[client_id].put({
                    'type': 'audio_input',
                    'client_id': client_id,
                    'data': message['media']['payload'],
                    'timestamp': message['media']['timestamp']
                })

            self.states[client_id]['last_activity'] = datetime.now()

        except KeyError as e:
            logger.error(f"Invalid media packet: {str(e)}")

    async def handle_openai_event(self, client_id: str, event: Dict):
        """Process OpenAI API events"""
        try:
            event_type = event.get('type', 'unknown')

            if event_type == 'transcript':
                await self.twilio_queues[client_id].put({
                    'type': 'response',
                    'text': event['text'],
                    'timestamp': datetime.now().timestamp()
                })

            elif event_type == 'audio_output':
                await self.active_connections[client_id].send_json({
                    'event': 'media',
                    'media': {
                        'payload': event['data'],
                        'timestamp': event['timestamp']
                    }
                })

            self.states[client_id]['last_response'] = datetime.now()

        except Exception as e:
            logger.error(f"OpenAI event handling failed: {str(e)}")

    async def handle_state_updates(self, client_id: str):
        """Manage client state changes"""
        state = self.states.get(client_id)
        if not state:
            return

        # Check for call expiration (5 minutes inactivity)
        if (datetime.now() - state['last_activity']).total_seconds() > 300:
            logger.info(f"Terminating idle call for {client_id}")
            await self.disconnect(client_id)

        # Update call status based on recent activity
        if state.get('call_ended'):
            state['call_status'] = 'terminated'
        elif state['media_counter'] > 0:
            state['call_status'] = 'active'

        # Trigger cleanup if needed
        if state['call_status'] == 'terminated':
            await self.disconnect(client_id)

    async def get_twilio_event(self, client_id: str) -> Optional[Dict]:
        """Retrieve the next Twilio event with timeout and error handling"""
        try:
            # Use a short timeout to prevent blocking
            return await asyncio.wait_for(
                self.twilio_queues[client_id].get(),
                timeout=0.1  # 100ms timeout
            )
        except asyncio.QueueEmpty:
            logger.debug(f"No Twilio events for {client_id}")
            return None
        except KeyError:
            logger.warning(f"Client queue missing for {client_id}")
            return None
        except asyncio.TimeoutError:
            logger.debug(f"Twilio event timeout for {client_id}")
            return None
        except Exception as e:
            logger.error(f"Twilio event error for {client_id}: {str(e)}")
            return None

    async def monitor_connections(self):
        while True:
            await asyncio.sleep(10)
            now = datetime.now()
            for client_id in list(self.states.keys()):
                last_active = self.states[client_id]["last_activity"]
                if (now - last_active).total_seconds() > 300:  # 5min timeout
                    await self.disconnect(client_id)

    async def check_websocket_health(self):
        while True:
            await asyncio.sleep(5)
            for client_id in list(self.active_connections.keys()):
                if self.active_connections[client_id].client_state != 1:  # 1 = CONNECTED
                    logger.warning(f"Reconnecting client {client_id}")
                    await self.disconnect(client_id)

    async def handle_twilio_start(self, client_id: str, stream_sid: str):
        """Handle Twilio stream start event"""
        self.stream_sids[client_id] = stream_sid
        await self.active_connections[client_id].send_json({
            "event": "connected",
            "streamSid": stream_sid
        })