import hark from "hark";

export class MediaStreamProcessor {
    private mediaRecorder: MediaRecorder | null = null;
    private stream: MediaStream | null = null;
    private speechEvents: any;
    private onDataAvailable: ((data: ArrayBuffer) => void) | null = null;

    async startStream(onDataAvailable: (data: ArrayBuffer) => void) {
        try {
            // Request both video and audio for preview.
            this.stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
            // Create an audio-only stream for recording.
            const audioStream = new MediaStream(this.stream.getAudioTracks());
            this.onDataAvailable = onDataAvailable;
            this.mediaRecorder = new MediaRecorder(audioStream, { mimeType: "audio/webm" });
            this.mediaRecorder.ondataavailable = async (event) => {
                if (event.data.size > 0) {
                    const arrayBuffer = await event.data.arrayBuffer();
                    if (this.onDataAvailable) {
                        this.onDataAvailable(arrayBuffer);
                    }
                }
            };

            // Set up Hark.js to detect speech events.
            this.speechEvents = hark(audioStream, { interval: 50, threshold: -50 });
            // When the user stops speaking, request data from the recorder.
            this.speechEvents.on("stopped_speaking", () => {
                console.log("[Hark] Detected silence. Requesting data.");
                if (this.mediaRecorder && this.mediaRecorder.state === "recording") {
                    this.mediaRecorder.requestData();
                }
            });

            // Start recording continuously (no fixed timeslice).
            this.mediaRecorder.start();
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
        if (this.speechEvents) {
            this.speechEvents.stop();
        }
        if (this.stream) {
            this.stream.getTracks().forEach((track) => track.stop());
        }
        this.stream = null;
        this.mediaRecorder = null;
        this.speechEvents = null;
    }
}

export const createMediaStreamProcessor = () => new MediaStreamProcessor();