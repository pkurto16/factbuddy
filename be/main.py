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
except ImportError:
    print("Please install openai-whisper: pip install openai-whisper")
    raise

fact_checker = FactCheckAgent(os.getenv("OPENAI_API_KEY"))

# Store active connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)

manager = ConnectionManager()

# Video storage setup
UPLOAD_DIR = Path("video_segments")
UPLOAD_DIR.mkdir(exist_ok=True)

async def save_video_chunk(data: bytes, session_id: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{session_id}_{timestamp}.webm"
    filepath = UPLOAD_DIR / filename

    async with aiofiles.open(filepath, 'wb') as f:
        await f.write(data)

    return str(filepath)

async def process_audio_chunk(filepath: str) -> str:
    """Process audio chunk using Whisper"""
    try:
        result = model.transcribe(filepath)
        return result["text"]
    except Exception as e:
        print(f"Transcription error: {e}")
        return ""

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message["type"] == "mediaChunk":
                # Decode and save video chunk
                media_data = base64.b64decode(message["data"].split(",")[1])
                video_path = await save_video_chunk(media_data, client_id)

                # Transcribe audio
                transcription = await process_audio_chunk(video_path)

                if transcription.strip():
                    # Send transcription result
                    await websocket.send_json({
                        "type": "transcription",
                        "text": transcription
                    })

                    # Start fact-checking process
                    await fact_checker.stream_fact_check(transcription, websocket)

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        print(f"Error: {e}")
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)