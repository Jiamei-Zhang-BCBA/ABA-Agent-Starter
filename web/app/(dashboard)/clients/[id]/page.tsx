"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Client, Job } from "@/types";

function formatTime(iso: string) {
  return new Date(iso).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  pending: { label: "等待中", color: "bg-gray-400" },
  processing: { label: "处理中", color: "bg-blue-400" },
  delivered: { label: "已完成", color: "bg-green-500" },
  failed: { label: "失败", color: "bg-red-500" },
};

interface TimelineEntry {
  job_id: string;
  feature_id: string;
  status: string;
  created_at: string;
  completed_at: string | null;
}

export default function ClientDetailPage() {
  const params = useParams();
  const clientId = params.id as string;
  const [client, setClient] = useState<Client | null>(null);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!clientId) return;
    Promise.all([
      api.get<Client>(`/clients/${clientId}`),
      api.get<{ timeline: TimelineEntry[] }>(`/clients/${clientId}/timeline`).catch(() => ({ timeline: [] })),
    ])
      .then(([c, t]) => {
        setClient(c);
        setTimeline(t.timeline || []);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [clientId]);

  if (loading) {
    return <div className="text-center py-12 text-gray-400">加载中...</div>;
  }

  if (!client) {
    return <div className="text-center py-12 text-gray-400">个案不存在</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-2xl font-bold text-gray-900">{client.code_name}</h1>
            <Badge variant={client.status === "active" ? "default" : "secondary"}>
              {client.status === "active" ? "活跃" : client.status}
            </Badge>
          </div>
          <p className="text-muted-foreground mt-1">别名：{client.display_alias}</p>
        </div>
        <Link href="/clients">
          <Button variant="outline">返回列表</Button>
        </Link>
      </div>

      <div>
        <h2 className="text-lg font-semibold mb-4">任务时间线</h2>
        {timeline.length === 0 ? (
          <div className="text-center py-8 text-gray-400">暂无任务记录</div>
        ) : (
          <div className="space-y-0">
            {timeline.map((entry, i) => {
              const s = STATUS_MAP[entry.status] || { label: entry.status, color: "bg-gray-400" };
              return (
                <div key={entry.job_id} className="flex items-start">
                  <div className="flex flex-col items-center mr-4">
                    <div className={`w-3 h-3 rounded-full ${s.color}`} />
                    {i < timeline.length - 1 && (
                      <div className="w-0.5 h-12 bg-gray-200" />
                    )}
                  </div>
                  <div className="pb-6">
                    <p className="font-medium text-sm">{entry.feature_id}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatTime(entry.created_at)}
                      {" · "}
                      {s.label}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
