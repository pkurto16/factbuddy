import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json
import os
from fact_checker.agent import FactCheckAgent
from typing import Dict
from datetime import datetime
from pathlib import Path
import aiofiles
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI()

# CORS configuration
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

# Store active connections
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

# Video storage setup
UPLOAD_DIR = Path("video_segments")
UPLOAD_DIR.mkdir(exist_ok=True)
logging.info(f"Video upload directory set to: {UPLOAD_DIR.resolve()}")

async def process_audio_chunk(filepath: str) -> str:
    """Process audio chunk using Whisper"""
    try:
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            logging.warning(f"Invalid or empty file: {filepath}")
            return ""
        logging.info(f"Processing audio chunk from file: {filepath}")
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
                    # Process other JSON messages if needed.
                except Exception as e:
                    logging.error(f"Error processing text message from client {client_id}: {e}")
                    await websocket.send_json({"type": "error", "message": str(e)})
            elif "bytes" in message:
                binary_data = message["bytes"]
                logging.info(f"Received binary data from client {client_id} (length: {len(binary_data)} bytes)")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{client_id}_{timestamp}.webm"
                filepath = UPLOAD_DIR / filename
                try:
                    async with aiofiles.open(filepath, 'wb') as f:
                        await f.write(binary_data)
                    logging.info(f"Saved raw binary video chunk to {filepath}")
                    transcription = await process_audio_chunk(str(filepath))
                    if transcription.strip():
                        await websocket.send_json({
                            "type": "transcription",
                            "text": transcription
                        })
                        await fact_checker.stream_fact_check(transcription, websocket)
                except Exception as e:
                    logging.error(f"Error saving or processing binary data for client {client_id}: {e}")
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
