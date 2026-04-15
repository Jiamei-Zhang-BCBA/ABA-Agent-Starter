import { useEffect, useRef } from "react";
import { useAuth } from "./auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

/**
 * Hook to subscribe to SSE job status updates.
 * Connects when jobId is provided and status is non-terminal.
 * Calls onStatus with each status change.
 */
export function useJobStream(
  jobId: string | null,
  onStatus: (status: string) => void,
) {
  const eventSourceRef = useRef<EventSource | null>(null);
  const { token } = useAuth();

  useEffect(() => {
    if (!jobId || !token) return;

    // EventSource doesn't support custom headers, so we use fetch-based SSE
    const controller = new AbortController();

    async function connect() {
      try {
        const res = await fetch(`${API_BASE}/jobs/${jobId}/stream`, {
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        });

        if (!res.ok || !res.body) return;

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.status) {
                  onStatus(data.status);
                }
              } catch {
                // ignore parse errors
              }
            }
            if (line.startsWith("event: complete")) {
              controller.abort();
              return;
            }
          }
        }
      } catch {
        // connection closed or aborted
      }
    }

    connect();

    return () => {
      controller.abort();
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, [jobId, token, onStatus]);
}
