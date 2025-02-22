import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json
import os
from fact_checker.agent import FactCheckAgent
from typing import Dict, List
import base64
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

async def save_video_chunk(data: str, session_id: str) -> str:
    try:
        logging.info(f"Saving video chunk for session {session_id}")
        # Remove the data URL prefix if present
        if ',' in data:
            logging.debug("Data URL prefix detected. Stripping prefix.")
            data = data.split(',')[1]

        logging.debug(f"Length of base64 data before padding: {len(data)}")
        # Add missing padding if necessary
        missing_padding = len(data) % 4
        if missing_padding:
            logging.debug(f"Base64 data length is not a multiple of 4. Adding {4 - missing_padding} '=' characters.")
            data += '=' * (4 - missing_padding)

        # Decode base64 data
        binary_data = base64.b64decode(data)
        logging.info(f"Decoded video chunk for session {session_id} (size: {len(binary_data)} bytes)")

        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{session_id}_{timestamp}.webm"
        filepath = UPLOAD_DIR / filename

        # Save the binary data
        async with aiofiles.open(filepath, 'wb') as f:
            await f.write(binary_data)
        logging.info(f"Video chunk saved to: {filepath}")

        return str(filepath)
    except Exception as e:
        logging.error(f"Error saving video chunk for session {session_id}: {e}")
        raise

async def process_audio_chunk(filepath: str) -> str:
    """Process audio chunk using Whisper"""
    try:
        # Make sure the file exists and has content
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
            data = await websocket.receive_text()
            logging.info(f"Received data from client {client_id}")
            try:
                message = json.loads(data)
                logging.debug(f"Message content: {message}")

                if message["type"] == "mediaChunk":
                    if not message.get("data"):
                        logging.warning("Received empty media chunk")
                        continue

                    # Save the video chunk
                    video_path = await save_video_chunk(message["data"], client_id)

                    # Process the audio
                    transcription = await process_audio_chunk(video_path)

                    if transcription.strip():
                        # Send transcription result
                        await websocket.send_json({
                            "type": "transcription",
                            "text": transcription
                        })
                        logging.info(f"Sent transcription to client {client_id}")

                        # Start fact-checking process
                        await fact_checker.stream_fact_check(transcription, websocket)

            except json.JSONDecodeError as e:
                logging.error(f"JSON decode error: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON message"
                })
            except Exception as e:
                logging.error(f"Error processing message from client {client_id}: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logging.error(f"WebSocket error for client {client_id}: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except Exception as ex:
            logging.error(f"Failed to send error message to client {client_id}: {ex}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)