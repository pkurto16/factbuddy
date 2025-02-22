export class MediaStreamProcessor {
    private mediaRecorder: MediaRecorder | null = null;
    private stream: MediaStream | null = null;

    async startStream(onDataAvailable: (data: ArrayBuffer) => void) {
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: true,
                audio: true,
            });

            this.mediaRecorder = new MediaRecorder(this.stream, {
                mimeType: "video/webm;codecs=vp8,opus",
            });

            this.mediaRecorder.ondataavailable = async (event) => {
                if (event.data.size > 0) {
                    const arrayBuffer = await event.data.arrayBuffer();
                    onDataAvailable(arrayBuffer);
                }
            };

            // Start recording with 1-second chunks
            this.mediaRecorder.start(1000);
            return this.stream;
        } catch (error) {
            console.error("Error accessing media devices:", error);
            throw error;
        }
    }

    stopStream() {
        if (this.mediaRecorder && this.mediaRecorder.state !== "inactive") {
            this.mediaRecorder.stop();
        }

        if (this.stream) {
            this.stream.getTracks().forEach((track) => track.stop());
        }
        this.stream = null;
        this.mediaRecorder = null;
    }
}

export const createMediaStreamProcessor = () => new MediaStreamProcessor();