import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2, ArrowUp, ArrowDown } from "lucide-react";
import type { FactCheckResult, FactCheckStatus, SearchResult, AnalysisUpdate } from "@/types/fact-check";

// Helper to safely extract hostname from a URL string
function safeHostname(url: string): string {
    try {
        return new URL(url).hostname;
    } catch (error) {
        return "Invalid URL";
    }
}

interface FactCheckDisplayProps {
    status?: FactCheckStatus;
    result?: FactCheckResult;
    searchResult?: SearchResult;
    analysisUpdate?: AnalysisUpdate;
}

export function FactCheckDisplay({ status, result, searchResult, analysisUpdate }: FactCheckDisplayProps) {
    const [expanded, setExpanded] = useState(false);

    if (!status && !result && !searchResult && !analysisUpdate) return null;

    let parsedCorrection;
    if (result && result.correction) {
        try {
            parsedCorrection = JSON.parse(result.correction);
        } catch (e) {
            parsedCorrection = null;
        }
    }

    return (
        <div
            className="cursor-pointer p-4 bg-black/80 text-white rounded shadow-lg transition-all duration-300 max-w-sm"
            onClick={() => setExpanded(!expanded)}
        >
            {result ? (
                <>
                    <div className="flex items-center justify-between">
                        <div className="text-sm font-medium truncate max-w-[150px]">
                            {result.statement}
                        </div>
                        <Badge variant="secondary" className="text-xs">
                            {result.truthScore ? result.truthScore.toFixed(1) + "%" : "N/A"}
                        </Badge>
                    </div>
                    {expanded && (
                        <div className="mt-2 text-xs">
                            {parsedCorrection ? (
                                <>
                                    <div className="mb-1">
                                        <strong>Summary:</strong> {parsedCorrection.summary}
                                    </div>
                                    <div className="mb-1">
                                        <strong>Verdict:</strong> {parsedCorrection.verdict}
                                    </div>
                                    <div className="mb-1">
                                        <strong>Credibility:</strong> {parsedCorrection.score}
                                    </div>
                                </>
                            ) : (
                                <div className="mb-1">{result.correction}</div>
                            )}
                            {result.sources && result.sources.length > 0 && (
                                <div>
                                    <div className="font-medium mb-1">Sources:</div>
                                    {result.sources.map((src, i) => (
                                        <div key={i} className="truncate">
                                            {src.url ? (
                                                <a
                                                    href={src.url}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="hover:underline"
                                                >
                                                    {src.title || safeHostname(src.url)}
                                                </a>
                                            ) : (
                                                <span>Unknown source</span>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                    <div className="mt-1 flex justify-end">
                        {expanded ? <ArrowDown size={16} /> : <ArrowUp size={16} />}
                    </div>
                </>
            ) : (
                <div className="flex flex-col items-center">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <div className="text-xs mt-1">{status ? status.message : "Fact-checking..."}</div>
                </div>
            )}
        </div>
    );
}