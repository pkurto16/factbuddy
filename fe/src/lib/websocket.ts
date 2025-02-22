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
        console.log("Attempting to connect to WebSocket:", this.url)
        this.ws = new WebSocket(this.url)

        this.ws.onopen = () => {
            console.log("WebSocket connection established")
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
            console.log("Received WebSocket message:", event.data)
            try {
                const data = JSON.parse(event.data)
                if (this.onMessageCallback) {
                    this.onMessageCallback(data)
                }
            } catch (error) {
                console.error("Error parsing WebSocket message:", error)
            }
        }
    }

    private attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++
            console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`)
            setTimeout(() => this.connect(), 1000 * this.reconnectAttempts)
        }
    }

    sendMessage(data: any) {
        if (this.ws?.readyState === WebSocket.OPEN) {
            const message = JSON.stringify(data)
            console.log("Sending WebSocket message:", message)
            this.ws.send(message)
        } else {
            console.warn("WebSocket is not open. Current state:", this.ws?.readyState)
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