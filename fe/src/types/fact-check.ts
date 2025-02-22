export interface BaseMessage {
    type: string
}

export interface TranscriptionResult extends BaseMessage {
    type: "transcription"
    text: string
}

export interface FactCheckStatus extends BaseMessage {
    type: "status"
    message: string
    phase: "context" | "search" | "sources" | "analysis" | "synthesis"
    progress?: number
}

export interface Source {
    url: string
    credibility: number
    title?: string
    snippet?: string
}

export interface FactCheckResult extends BaseMessage {
    type: "factCheck"
    statement: string
    truthScore: number
    correction: string
    sources: Source[]
    timestamp: string
}

export interface SearchResult extends BaseMessage {
    type: "search"
    query: string
    sources: string[]
}

export interface AnalysisUpdate extends BaseMessage {
    type: "analysis"
    source: string
    credibility: number
    summary: string
}

export interface ErrorMessage extends BaseMessage {
    type: "error"
    message: string
}

export type WebSocketMessage =
    | TranscriptionResult
    | FactCheckStatus
    | FactCheckResult
    | SearchResult
    | AnalysisUpdate
    | ErrorMessage