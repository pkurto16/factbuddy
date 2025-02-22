import { WebSocketServer } from "ws"
import { createServer } from "http"

const wss = new WebSocketServer({ noServer: true })

wss.on("connection", (ws) => {
    console.log("Client connected")

    ws.on("message", async (message) => {
        try {
            const data = JSON.parse(message.toString())

            if (data.type === "mediaChunk") {
                // Process the media chunk
                // 1. Convert to audio
                // 2. Perform transcription
                // 3. Check facts
                // 4. Send results back

                // Simulate transcription result
                ws.send(
                    JSON.stringify({
                        type: "transcription",
                        text: "Processing transcription...",
                    }),
                )

                // Simulate fact check result after processing
                setTimeout(() => {
                    ws.send(
                        JSON.stringify({
                            type: "factCheck",
                            statement: "Processed statement",
                            truthScore: Math.random() * 100,
                            correction: "Fact check result",
                            videoUrl: "/api/video/segment-1.webm",
                        }),
                    )
                }, 2000)
            }
        } catch (error) {
            console.error("Error processing message:", error)
            ws.send(JSON.stringify({ type: "error", message: "Error processing request" }))
        }
    })

    ws.on("close", () => {
        console.log("Client disconnected")
    })
})

const server = createServer()

server.on("upgrade", (request, socket, head) => {
    wss.handleUpgrade(request, socket, head, (ws) => {
        wss.emit("connection", ws, request)
    })
})

export default function handler(req: any, res: any) {
    if (!res.socket.server.ws) {
        res.socket.server.ws = true
        server.listen(process.env.PORT || 3001)
    }
    res.end()
}

