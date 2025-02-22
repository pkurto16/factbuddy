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


async def save_video_chunk(data: str, session_id: str) -> str:
    """Save a base64 encoded video chunk to file"""
    try:
        # Remove the data URL prefix if present
        if ',' in data:
            data = data.split(',')[1]

        # Decode base64 data
        binary_data = base64.b64decode(data)

        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{session_id}_{timestamp}.webm"
        filepath = UPLOAD_DIR / filename

        # Save the binary data
        async with aiofiles.open(filepath, 'wb') as f:
            await f.write(binary_data)

        return str(filepath)
    except Exception as e:
        print(f"Error saving video chunk: {e}")
        raise


async def process_audio_chunk(filepath: str) -> str:
    """Process audio chunk using Whisper"""
    try:
        # Make sure the file exists and has content
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            print(f"Invalid or empty file: {filepath}")
            return ""

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
            try:
                message = json.loads(data)

                if message["type"] == "mediaChunk":
                    if not message.get("data"):
                        print("Received empty media chunk")
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

                        # Start fact-checking process
                        await fact_checker.stream_fact_check(transcription, websocket)

            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON message"
                })
            except Exception as e:
                print(f"Error processing message: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass  # Connection might be already closed


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)