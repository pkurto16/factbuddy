import logging
import json
import os
import asyncio
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
client_statements: Dict[str, str] = {}  # Aggregated transcription per client
last_fact_checked_statement: Dict[str, str] = {}

# Audio storage setup
UPLOAD_DIR = Path("audio_segments")
UPLOAD_DIR.mkdir(exist_ok=True)
logging.info(f"Audio upload directory set to: {UPLOAD_DIR.resolve()}")


async def process_audio_chunk(filepath: str) -> str:
    """Process audio chunk using Whisper and return the transcription.
       File deletion is handled later in the endpoint.
    """
    try:
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            logging.warning(f"Invalid or empty file: {filepath}")
            return ""
        logging.info(f"Processing audio file: {filepath}")
        # Wait a bit longer (0.5 sec) to help ensure the file is complete.
        await asyncio.sleep(0.5)
        result = model.transcribe(filepath)
        text = result["text"]
        logging.info(f"Transcription result: {text}")
        return text
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
                    # Handle JSON commands if needed.
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

                    # Delete the file AFTER transcription is processed.
                    try:
                        os.remove(filepath)
                        logging.info(f"Deleted file: {filepath}")
                    except Exception as del_e:
                        logging.error(f"Error deleting file {filepath}: {del_e}")

                    if transcription.strip():
                        # Send individual transcription to the client.
                        await websocket.send_json({
                            "type": "transcription",
                            "text": transcription
                        })
                        logging.info(f"Transcribed chunk for client {client_id}: {transcription}")

                        # Append the transcription to the client's running statement.
                        current = client_statements.get(client_id, "")
                        new_running = (current + " " + transcription).strip()
                        client_statements[client_id] = new_running
                        logging.info(f"Updated running statement for client {client_id}: {new_running}")

                        # Evaluate if the running statement forms a complete fact statement.
                        evaluation = await fact_checker.evaluate_fact_statement(new_running)
                        logging.info(f"Evaluation result for client {client_id}: {evaluation}")

                        if evaluation.get("complete"):
                            asyncio.create_task(fact_checker.stream_fact_check(new_running, websocket))
                            if evaluation.get("action") == "new":
                                logging.info(f"Starting new fact for client {client_id}. Resetting running statement.")
                                client_statements[client_id] = ""
                            else:
                                logging.info(f"Continuing current fact for client {client_id}.")
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