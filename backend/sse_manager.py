"""
SSE Manager for handling Server-Sent Events
"""
import json
import logging
from typing import Dict, Any, Optional
from flask import Response
import queue
import threading

logger = logging.getLogger(__name__)


class SSEManager:
    """Manager for Server-Sent Events broadcasting"""
    
    def __init__(self, socketio=None):
        """Initialize SSE Manager
        
        Args:
            socketio: Flask-SocketIO instance for WebSocket fallback
        """
        self.socketio = socketio
        self.clients: Dict[str, queue.Queue] = {}
        self.lock = threading.Lock()
        
    def register_client(self, client_id: str) -> queue.Queue:
        """Register a new SSE client
        
        Args:
            client_id: Unique identifier for the client
            
        Returns:
            Queue for this client's events
        """
        with self.lock:
            if client_id not in self.clients:
                self.clients[client_id] = queue.Queue()
            return self.clients[client_id]
    
    def unregister_client(self, client_id: str):
        """Unregister an SSE client
        
        Args:
            client_id: Client identifier to remove
        """
        with self.lock:
            self.clients.pop(client_id, None)
    
    def broadcast(self, event_type: str, data: Dict[str, Any], namespace: str = '/game'):
        """Broadcast an event to all connected clients
        
        Args:
            event_type: Type of event to broadcast
            data: Event data to send
            namespace: Namespace for the event
        """
        # Use SocketIO if available
        if self.socketio:
            self.socketio.emit(event_type, data, namespace=namespace)
        
        # Also queue for SSE clients
        event_data = {
            'type': event_type,
            'data': data
        }
        
        with self.lock:
            for client_queue in self.clients.values():
                try:
                    client_queue.put_nowait(event_data)
                except queue.Full:
                    logger.warning(f"Client queue full, dropping event {event_type}")
    
    def send_to_client(self, client_id: str, event_type: str, data: Dict[str, Any]):
        """Send an event to a specific client
        
        Args:
            client_id: Target client identifier
            event_type: Type of event to send
            data: Event data
        """
        with self.lock:
            if client_id in self.clients:
                event_data = {
                    'type': event_type,
                    'data': data
                }
                try:
                    self.clients[client_id].put_nowait(event_data)
                except queue.Full:
                    logger.warning(f"Client {client_id} queue full, dropping event {event_type}")
    
    async def send_event(self, event_or_type, payload: Optional[Any] = None, namespace: str = '/game'):
        """Async-compatible helper to send/broadcast an event.
        
        Supports two calling patterns:
        - send_event({"type": "my_event", ...})
        - send_event("my_event", payload_dict_or_json_string)
        
        Args:
            event_or_type: Either a dict containing at least a 'type' key, or the event type string
            payload: Optional payload if event_or_type is a string type
            namespace: SocketIO namespace
        """
        try:
            # Case 1: dict with embedded type
            if isinstance(event_or_type, dict):
                evt_type = event_or_type.get('type', 'event')
                self.broadcast(evt_type, event_or_type, namespace=namespace)
                return
            
            # Case 2: explicit type + payload
            evt_type = str(event_or_type)
            data: Dict[str, Any]
            if isinstance(payload, str):
                try:
                    data = json.loads(payload)
                except Exception:
                    # Fallback: wrap raw string
                    data = {"message": payload}
            elif isinstance(payload, dict):
                data = payload
            else:
                data = {"data": payload}
            
            self.broadcast(evt_type, data, namespace=namespace)
        except Exception as e:
            logger.error(f"send_event error for {event_or_type}: {e}")
    
    def stream_events(self, client_id: str):
        """Generator for SSE streaming
        
        Args:
            client_id: Client to stream events to
            
        Yields:
            SSE formatted events
        """
        client_queue = self.register_client(client_id)
        
        try:
            while True:
                try:
                    # Wait for events with timeout
                    event = client_queue.get(timeout=30)
                    
                    # Format as SSE
                    yield f"event: {event['type']}\n"
                    yield f"data: {json.dumps(event['data'])}\n\n"
                    
                except queue.Empty:
                    # Send heartbeat to keep connection alive
                    yield f"event: heartbeat\ndata: {{}}\n\n"
                    
        except GeneratorExit:
            self.unregister_client(client_id)
        except Exception as e:
            logger.error(f"Error streaming to client {client_id}: {e}")
            self.unregister_client(client_id)
