"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { StaffAssignmentPanel } from "@/components/staff-assignment-panel";
import type { Client } from "@/types";

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
  submitted_by: string;
  created_at: string;
  completed_at: string | null;
  has_output: boolean;
}

interface TimelineResponse {
  client: Client;
  timeline: TimelineEntry[];
  vault_files: Record<string, string[]>;
  total_jobs: number;
  completed_jobs: number;
}

export default function ClientDetailPage() {
  const params = useParams();
  const clientId = params.id as string;
  const [data, setData] = useState<TimelineResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!clientId) return;
    api
      .get<TimelineResponse>(`/clients/${clientId}/timeline`)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [clientId]);

  if (loading) {
    return <div className="text-center py-12 text-gray-400">加载中...</div>;
  }

  if (!data) {
    return <div className="text-center py-12 text-gray-400">个案不存在或无权访问</div>;
  }

  const { client, timeline, vault_files, total_jobs, completed_jobs } = data;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-2xl font-bold text-gray-900">{client.code_name}</h1>
            <Badge variant={client.status === "active" ? "default" : "secondary"}>
              {client.status === "active" ? "活跃" : client.status}
            </Badge>
          </div>
          <p className="text-muted-foreground mt-1">
            别名：{client.display_alias} · 任务 {completed_jobs}/{total_jobs}
          </p>
        </div>
        <Link href="/clients">
          <Button variant="outline">返回列表</Button>
        </Link>
      </div>

      {/* Tabs: Timeline / Team / Files */}
      <Tabs defaultValue="timeline">
        <TabsList>
          <TabsTrigger value="timeline">时间线</TabsTrigger>
          <TabsTrigger value="team">团队</TabsTrigger>
          <TabsTrigger value="files">文件库</TabsTrigger>
        </TabsList>

        {/* Timeline Tab */}
        <TabsContent value="timeline" className="mt-4">
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
                        {" · "}
                        提交者: {entry.submitted_by}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </TabsContent>

        {/* Team Tab */}
        <TabsContent value="team" className="mt-4">
          <StaffAssignmentPanel clientId={clientId} />
        </TabsContent>

        {/* Files Tab */}
        <TabsContent value="files" className="mt-4">
          {Object.keys(vault_files).length === 0 ? (
            <div className="text-center py-8 text-gray-400">暂无文件</div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {Object.entries(vault_files).map(([label, files]) => (
                <Card key={label}>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">{label}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {files.length === 0 ? (
                      <p className="text-sm text-gray-400">暂无文件</p>
                    ) : (
                      <ul className="space-y-1">
                        {files.map((f) => (
                          <li key={f} className="text-sm text-gray-700 flex items-center">
                            <span className="mr-2">📄</span>
                            {f}
                          </li>
                        ))}
                      </ul>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
