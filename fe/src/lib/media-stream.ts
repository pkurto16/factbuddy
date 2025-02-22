export class MediaStreamProcessor {
    private mediaRecorder: MediaRecorder | null = null;
    private stream: MediaStream | null = null;

    async startStream(onDataAvailable: (data: ArrayBuffer) => void) {
        try {
            // Request both video and audio for preview
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: true,
                audio: true,
            });
            // For recording, use only the audio tracks.
            const audioStream = new MediaStream(this.stream.getAudioTracks());
            this.mediaRecorder = new MediaRecorder(audioStream, {
                mimeType: "audio/webm",
            });

            this.mediaRecorder.ondataavailable = async (event) => {
                if (event.data.size > 0) {
                    const arrayBuffer = await event.data.arrayBuffer();
                    onDataAvailable(arrayBuffer);
                }
            };

            // Start recording with larger chunks (e.g. 5000ms = 5 seconds)
            this.mediaRecorder.start(5000);
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