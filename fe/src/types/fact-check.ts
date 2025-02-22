export interface FactCheckStatus {
    type: "status"
    message: string
    phase: "context" | "search" | "sources" | "analysis" | "synthesis"
}

export interface FactCheckResult {
    type: "factCheck"
    statement: string
    truthScore: number
    correction: string
    sources: Array<{
        url: string
        credibility: number
    }>
    timestamp: string
}

export interface TranscriptionResult {
    type: "transcription"
    text: string
}

export type WebSocketMessage = FactCheckStatus | FactCheckResult | TranscriptionResult

