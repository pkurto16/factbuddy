"use client"

import { useState, useRef, useEffect } from "react";
import { Camera, History, Mic, PauseCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Card } from "@/components/ui/card";
import { createWebSocketClient } from "@/lib/websocket";
import { createMediaStreamProcessor } from "@/lib/media-stream";
import { FactCheckDisplay } from "@/components/fact-check-display";
import type {
  FactCheckResult,
  FactCheckStatus,
  SearchResult,
  AnalysisUpdate,
  WebSocketMessage,
} from "@/types/fact-check";

export default function FactCheckPage() {
  const [isRecording, setIsRecording] = useState(false);
  const [activeTab, setActiveTab] = useState<"live" | "history">("live");
  const [currentTranscript, setCurrentTranscript] = useState<string>("");
  const [factCheckStatus, setFactCheckStatus] = useState<FactCheckStatus>();
  const [currentFactCheck, setCurrentFactCheck] = useState<FactCheckResult>();
  const [factCheckHistory, setFactCheckHistory] = useState<FactCheckResult[]>([]);
  const [searchResult, setSearchResult] = useState<SearchResult>();
  const [analysisUpdate, setAnalysisUpdate] = useState<AnalysisUpdate>();

  const videoRef = useRef<HTMLVideoElement>(null);
  const wsRef = useRef<ReturnType<typeof createWebSocketClient> | null>(null);
  const mediaProcessorRef = useRef<ReturnType<typeof createMediaStreamProcessor> | null>(null);
  const clientId = useRef<string>(Math.random().toString(36).substring(7));

  useEffect(() => {
    const wsUrl = `${process.env.NEXT_PUBLIC_WEBSOCKET_URL}/ws/${clientId.current}`;
    console.log("[WebSocket] Initializing client with URL:", wsUrl);
    wsRef.current = createWebSocketClient(wsUrl);
    mediaProcessorRef.current = createMediaStreamProcessor();

    wsRef.current.onMessage((data: WebSocketMessage) => {
      console.log("[WebSocket] Received message from API:", data);
      switch (data.type) {
        case "transcription":
          console.log("[WebSocket] Transcription received:", data.text);
          setCurrentTranscript(data.text);
          break;
        case "status":
          console.log("[WebSocket] Status update received:", data);
          setFactCheckStatus(data);
          break;
        case "search":
          console.log("[WebSocket] Search update received:", data);
          setSearchResult(data);
          break;
        case "analysis":
          console.log("[WebSocket] Analysis update received:", data);
          setAnalysisUpdate(data);
          break;
        case "factCheck":
          console.log("[WebSocket] Final fact check result received:", data);
          setCurrentFactCheck(data);
          setFactCheckHistory((prev) => [data, ...prev]);
          break;
        case "error":
          console.error("[WebSocket] Error received from API:", data.message);
          break;
        default:
          console.warn("[WebSocket] Unknown message type received:", data);
          break;
      }
    });

    wsRef.current.connect();
    console.log("[WebSocket] Connection initiated.");

    return () => {
      console.log("[WebSocket] Closing connection and stopping recording.");
      wsRef.current?.close();
      stopRecording();
    };
  }, []);

  const startRecording = async () => {
    try {
      console.log("[Recording] Starting recording...");
      if (!mediaProcessorRef.current || !wsRef.current) {
        console.error("[Recording] Media processor or WebSocket client not initialized.");
        return;
      }
      const stream = await mediaProcessorRef.current.startStream((data: ArrayBuffer) => {
        console.log("[Recording] Sending raw binary media chunk (length):", data.byteLength);
        wsRef.current?.sendMessage(data);
      });

      if (videoRef.current && stream) {
        videoRef.current.srcObject = stream;
        console.log("[Recording] Video element source set.");
      }
      setIsRecording(true);
      console.log("[Recording] Recording started.");
    } catch (err) {
      console.error("[Recording] Error starting recording:", err);
    }
  };

  const stopRecording = () => {
    console.log("[Recording] Stopping recording...");
    if (mediaProcessorRef.current) {
      mediaProcessorRef.current.stopStream();
      console.log("[Recording] Media stream stopped.");
    }
    if (videoRef.current?.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream;
      stream.getTracks().forEach((track) => track.stop());
      console.log("[Recording] Video stream tracks stopped.");
    }
    setIsRecording(false);
    setCurrentTranscript("");
    setCurrentFactCheck(undefined);
    setFactCheckStatus(undefined);
    console.log("[Recording] Recording state reset.");
  };

  return (
      <main className="min-h-screen bg-slate-700 text-white p-4">
        <div className="max-w-md mx-auto space-y-4">
          {/* Camera Preview */}
          <div className="relative aspect-[9/16] bg-black/20 rounded-lg overflow-hidden">
            <video ref={videoRef} autoPlay playsInline muted className="absolute inset-0 w-full h-full object-cover" />
            {/* Recording Controls */}
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex gap-4">
              <Button
                  size="lg"
                  variant={isRecording ? "destructive" : "default"}
                  className="rounded-full"
                  onClick={isRecording ? stopRecording : startRecording}
              >
                {isRecording ? <PauseCircle className="w-6 h-6 mr-2" /> : <Camera className="w-6 h-6 mr-2" />}
                {isRecording ? "Stop" : "Start"} Recording
              </Button>
            </div>
            {/* Live Transcription */}
            {isRecording && currentTranscript && (
                <div className="absolute top-4 left-4 right-4">
                  <Card className="bg-black/40 backdrop-blur-sm border-none p-4">
                    <p className="text-sm opacity-80">{"I'm hearing..."}</p>
                    <p className="text-lg">{currentTranscript}</p>
                  </Card>
                </div>
            )}
            {/* Live Fact Check Results */}
            {isRecording && (factCheckStatus || searchResult || analysisUpdate || currentFactCheck) && (
                <div className="absolute bottom-24 left-4 right-4">
                  <FactCheckDisplay
                      status={factCheckStatus}
                      result={currentFactCheck}
                      searchResult={searchResult}
                      analysisUpdate={analysisUpdate}
                  />
                </div>
            )}
          </div>
          {/* Tab Buttons */}
          <div className="flex gap-2">
            <Button
                variant={activeTab === "live" ? "secondary" : "ghost"}
                className="flex-1"
                onClick={() => {
                  console.log("[UI] Switching to live tab");
                  setActiveTab("live");
                }}
            >
              <Mic className="w-4 h-4 mr-2" />
              Live
            </Button>
            <Button
                variant={activeTab === "history" ? "secondary" : "ghost"}
                className="flex-1"
                onClick={() => {
                  console.log("[UI] Switching to history tab");
                  setActiveTab("history");
                }}
            >
              <History className="w-4 h-4 mr-2" />
              History
            </Button>
          </div>
          {/* History Section */}
          {activeTab === "history" && (
              <ScrollArea className="h-[300px]">
                <div className="space-y-4">
                  {factCheckHistory.map((result, index) => (
                      <FactCheckDisplay key={index} result={result} />
                  ))}
                </div>
              </ScrollArea>
          )}
        </div>
      </main>
  );
}