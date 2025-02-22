// Update WebSocket URL to point to FastAPI backend
const WEBSOCKET_URL = process.env.NEXT_PUBLIC_WEBSOCKET_URL || "ws://localhost:8000/ws"

class WebSocketClient {
    private ws: WebSocket | null = null
    private url: string
    private reconnectAttempts = 0
    private maxReconnectAttempts = 5
    private onMessageCallback: ((data: any) => void) | null = null

    constructor(url: string) {
        this.url = url
    }

    connect() {
        this.ws = new WebSocket(this.url)

        this.ws.onopen = () => {
            console.log("Connected to WebSocket")
            this.reconnectAttempts = 0
        }

        this.ws.onclose = () => {
            console.log("WebSocket connection closed")
            this.attemptReconnect()
        }

        this.ws.onerror = (error) => {
            console.error("WebSocket error:", error)
        }

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data)
            if (this.onMessageCallback) {
                this.onMessageCallback(data)
            }
        }
    }

    private attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++
            setTimeout(() => this.connect(), 1000 * this.reconnectAttempts)
        }
    }

    sendMessage(data: any) {
        if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data))
        }
    }

    onMessage(callback: (data: any) => void) {
        this.onMessageCallback = callback
    }

    close() {
        if (this.ws) {
            this.ws.close()
        }
    }
}

export const createWebSocketClient = (url: string = WEBSOCKET_URL) => new WebSocketClient(url)