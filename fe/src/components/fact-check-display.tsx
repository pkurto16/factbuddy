import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { AlertCircle, CheckCircle, Loader2 } from "lucide-react"
import type { FactCheckResult, FactCheckStatus } from "@/types/fact-check"

interface FactCheckDisplayProps {
    status?: FactCheckStatus
    result?: FactCheckResult
}

export function FactCheckDisplay({ status, result }: FactCheckDisplayProps) {
    if (!status && !result) return null

    return (
        <Card className="bg-black/40 backdrop-blur-sm border-none p-4 space-y-2">
            {status && (
                <div className="flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span className="text-sm opacity-80">{status.message}</span>
                    </div>
            )}

    {result && (
        <>
            <div className="flex items-center justify-between">
        <Badge
            variant="secondary"
        className={
                result.truthScore > 80 ? "bg-emerald-500" : result.truthScore > 40 ? "bg-yellow-500" : "bg-red-500"
            }
            >
            {result.truthScore.toFixed(1)}% True
            </Badge>
            <div className="flex items-center gap-2">
        {result.truthScore > 80 ? (
                <CheckCircle className="w-4 h-4 text-emerald-500" />
            ) : (
                <AlertCircle className="w-4 h-4 text-yellow-500" />
            )}
        </div>
        </div>

        <div className="space-y-2">
    <p className="text-sm font-medium">{result.statement}</p>
        <p className="text-sm opacity-80">{result.correction}</p>

        {result.sources.length > 0 && (
            <div className="text-xs opacity-60 space-y-1">
            <p className="font-medium">Sources:</p>
            {result.sources.map((source, i) => (
                <div key={i} className="flex items-center justify-between">
            <a
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:underline truncate max-w-[200px]"
                    >
                    {new URL(source.url).hostname}
                    </a>
                    <span>Credibility: {source.credibility.toFixed(1)}%</span>
            </div>
            ))}
            </div>
        )}
        </div>
        </>
    )}
    </Card>
)
}

