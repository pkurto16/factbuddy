export class MediaStreamProcessor {
    private mediaRecorder: MediaRecorder | null = null
    private chunks: Blob[] = []
    private stream: MediaStream | null = null
    private ws: WebSocket | null = null

    async startStream(onDataAvailable: (data: string) => void) {
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: true,
                audio: true,
            })

            this.mediaRecorder = new MediaRecorder(this.stream, {
                mimeType: "video/webm;codecs=vp8,opus",
            })

            this.mediaRecorder.ondataavailable = async (event) => {
                if (event.data.size > 0) {
                    this.chunks.push(event.data)
                    // Convert blob to base64
                    const base64data = await this.blobToBase64(event.data)
                    onDataAvailable(base64data)
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

    private blobToBase64(blob: Blob): Promise<string> {
        return new Promise((resolve, reject) => {
            const reader = new FileReader()
            reader.onloadend = () => {
                if (typeof reader.result === "string") {
                    resolve(reader.result)
                } else {
                    reject(new Error("Failed to convert blob to base64"))
                }
            }
            reader.onerror = reject
            reader.readAsDataURL(blob)
        })
    }

    stopStream() {
        if (this.mediaRecorder && this.mediaRecorder.state !== "inactive") {
            this.mediaRecorder.stop()
        }

        if (this.stream) {
            this.stream.getTracks().forEach((track) => track.stop())
        }

        this.chunks = []
        this.stream = null
        this.mediaRecorder = null
    }

    getRecordedBlob(): Blob | null {
        if (this.chunks.length === 0) return null
        return new Blob(this.chunks, { type: "video/webm" })
    }
}

export const createMediaStreamProcessor = () => new MediaStreamProcessor()