export class MediaStreamProcessor {
    private mediaRecorder: MediaRecorder | null = null
    private chunks: Blob[] = []
    private stream: MediaStream | null = null
    private processingInterval: NodeJS.Timer | null = null

    async startStream(onDataAvailable: (data: Blob) => void) {
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: true,
                audio: true,
            })

            this.mediaRecorder = new MediaRecorder(this.stream, {
                mimeType: "video/webm;codecs=vp8,opus",
            })

            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.chunks.push(event.data)
                    onDataAvailable(event.data)
                }
            }

            // Start recording with 1-second chunks
            this.mediaRecorder.start(1000)

            return this.stream
        } catch (error) {
            console.error("Error accessing media devices:", error)
            throw error
        }
    }

    stopStream() {
        if (this.mediaRecorder && this.mediaRecorder.state !== "inactive") {
            this.mediaRecorder.stop()
        }

        if (this.stream) {
            this.stream.getTracks().forEach((track) => track.stop())
        }

        if (this.processingInterval) {
            clearInterval(this.processingInterval)
        }

        this.chunks = []
        this.stream = null
        this.mediaRecorder = null
    }

    getRecordedBlob(): Blob | null {
        if (this.chunks.length === 0) return null
        return new Blob(this.chunks, { type: "video/webm" })
    }

    // Update the sendMessage method to encode media data as base64
    sendMessage(data: Blob) {
        const reader = new FileReader()
        reader.onload = () => {
            if (this.ws?.readyState === WebSocket.OPEN) {
                this.ws.send(
                    JSON.stringify({
                        type: "mediaChunk",
                        data: reader.result,
                    }),
                )
            }
        }
        reader.readAsDataURL(data)
    }
}

export const createMediaStreamProcessor = () => new MediaStreamProcessor()