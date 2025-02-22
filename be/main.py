import logging
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict

import aiofiles
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from fact_checker.agent import FactCheckAgent

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI()

# CORS configuration
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    import whisper

    model = whisper.load_model("base")
    logging.info("Whisper model loaded successfully")
except ImportError:
    logging.error("Please install openai-whisper: pip install openai-whisper")
    raise

fact_checker = FactCheckAgent(os.getenv("OPENAI_API_KEY"))


# Connection management
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logging.info(f"Client {client_id} connected.")

    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)
        logging.info(f"Client {client_id} disconnected.")


manager = ConnectionManager()

# Global dictionaries for per-client running statements.
client_statements: Dict[str, str] = {}
last_fact_checked_statement: Dict[str, str] = {}

# Audio storage setup
UPLOAD_DIR = Path("audio_segments")
UPLOAD_DIR.mkdir(exist_ok=True)
logging.info(f"Audio upload directory set to: {UPLOAD_DIR.resolve()}")


async def process_audio_chunk(filepath: str) -> str:
    """Process audio chunk using Whisper."""
    try:
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            logging.warning(f"Invalid or empty file: {filepath}")
            return ""
        logging.info(f"Processing audio file: {filepath}")
        result = model.transcribe(filepath)
        logging.info(f"Transcription result: {result['text']}")
        return result["text"]
    except Exception as e:
        logging.error(f"Transcription error for file {filepath}: {e}")
        return ""


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            message = await websocket.receive()
            if "text" in message:
                try:
                    data = json.loads(message["text"])
                    logging.info(f"Received text message from client {client_id}: {data}")
                    # (Handle JSON messages if needed)
                except Exception as e:
                    logging.error(f"Error processing text message from client {client_id}: {e}")
                    await websocket.send_json({"type": "error", "message": str(e)})
            elif "bytes" in message:
                binary_data = message["bytes"]
                logging.info(f"Received binary audio data from client {client_id} (length: {len(binary_data)} bytes)")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{client_id}_{timestamp}.webm"
                filepath = UPLOAD_DIR / filename
                try:
                    async with aiofiles.open(filepath, 'wb') as f:
                        await f.write(binary_data)
                    logging.info(f"Saved audio file to {filepath}")
                    transcription = await process_audio_chunk(str(filepath))
                    if transcription.strip():
                        # Send transcription of this chunk
                        await websocket.send_json({
                            "type": "transcription",
                            "text": transcription
                        })
                        logging.info(f"Fact-checking individual chunk for client {client_id}: {transcription}")
                        # Fact-check the individual chunk (run as a background task)
                        import asyncio
                        asyncio.create_task(fact_checker.stream_fact_check(transcription, websocket))

                        # Update the running statement for this client
                        current = client_statements.get(client_id, "")
                        new_running = (current + " " + transcription).strip()
                        client_statements[client_id] = new_running
                        logging.info(f"Updated running statement for client {client_id}: {new_running}")

                        # Only re-run fact-checking on the running statement if it has changed
                        if new_running != last_fact_checked_statement.get(client_id, ""):
                            last_fact_checked_statement[client_id] = new_running
                            logging.info(f"Fact-checking running statement for client {client_id}: {new_running}")
                            asyncio.create_task(fact_checker.stream_fact_check(new_running, websocket))
                except Exception as e:
                    logging.error(f"Error saving or processing binary audio for client {client_id}: {e}")
                    await websocket.send_json({"type": "error", "message": str(e)})
            else:
                logging.warning(f"Received unknown message type from client {client_id}: {message}")
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logging.error(f"WebSocket error for client {client_id}: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception as ex:
            logging.error(f"Failed to send error message to client {client_id}: {ex}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)