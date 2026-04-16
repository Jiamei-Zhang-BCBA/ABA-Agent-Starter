"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { StaffAssignmentPanel } from "@/components/staff-assignment-panel";
import { VaultFileViewer } from "@/components/vault-file-viewer";
import { getFeatureName } from "@/lib/feature-names";
import {
  FolderOpen, ClipboardCheck, Mail, Zap, BookOpen,
  UserPlus, BarChart3, Target, Brain, Sparkles, Award,
} from "lucide-react";
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
  queued: { label: "排队中", color: "bg-gray-400" },
  parsing: { label: "解析中", color: "bg-yellow-400" },
  processing: { label: "处理中", color: "bg-blue-400" },
  pending_review: { label: "待审核", color: "bg-orange-400" },
  approved: { label: "已审核", color: "bg-green-500" },
  delivered: { label: "已完成", color: "bg-green-500" },
  rejected: { label: "已退回", color: "bg-red-400" },
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

// Quick action definitions for the "操作" tab
const ICON_MAP: Record<string, React.ElementType> = {
  "clipboard-check": ClipboardCheck,
  "mail-heart": Mail,
  "zap": Zap,
  "book-open": BookOpen,
  "user-plus": UserPlus,
  "bar-chart": BarChart3,
  "target": Target,
  "brain": Brain,
  "sparkles": Sparkles,
  "award": Award,
};

interface QuickAction {
  featureId: string;
  label: string;
  icon: string;
  description: string;
}

const QUICK_ACTIONS: QuickAction[] = [
  { featureId: "session_review", label: "课后记录分析", icon: "clipboard-check", description: "分析老师提交的课后记录" },
  { featureId: "parent_letter", label: "写家书", icon: "mail-heart", description: "生成家长反馈信" },
  { featureId: "quick_summary", label: "战前简报", icon: "zap", description: "会议前快速汇总个案情报" },
  { featureId: "teacher_guide", label: "实操指引", icon: "book-open", description: "为老师生成实操小抄" },
  { featureId: "assessment", label: "评估记录", icon: "bar-chart", description: "录入并分析评估数据" },
  { featureId: "fba", label: "功能行为分析", icon: "brain", description: "分析问题行为的功能" },
  { featureId: "plan_generator", label: "制定IEP", icon: "target", description: "生成个别化教育计划" },
  { featureId: "reinforcer", label: "强化物评估", icon: "sparkles", description: "更新强化物偏好清单" },
  { featureId: "milestone_report", label: "阶段报告", icon: "award", description: "生成里程碑报告和喜报" },
];

export default function ClientDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { user } = useAuth();
  const clientId = params.id as string;
  const [data, setData] = useState<TimelineResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [viewerPath, setViewerPath] = useState<string | null>(null);
  const [viewerOpen, setViewerOpen] = useState(false);

  // Visible features for this user
  const [visibleFeatureIds, setVisibleFeatureIds] = useState<string[]>([]);

  useEffect(() => {
    if (!clientId) return;
    api
      .get<TimelineResponse>(`/clients/${clientId}/timeline`)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [clientId]);

  // Fetch user's visible features to filter quick actions
  useEffect(() => {
    api
      .get<{ features: Array<{ id: string }> }>("/features")
      .then((res) => setVisibleFeatureIds(res.features.map((f) => f.id)))
      .catch(() => {});
  }, []);

  function openFileViewer(dirLabel: string, filename: string) {
    const path = `${dirLabel}/${filename}`;
    setViewerPath(path);
    setViewerOpen(true);
  }

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

      {/* Tabs: Actions / Timeline / Team / Files */}
      <Tabs defaultValue="actions">
        <TabsList>
          <TabsTrigger value="actions">操作</TabsTrigger>
          <TabsTrigger value="timeline">时间线</TabsTrigger>
          <TabsTrigger value="team">团队</TabsTrigger>
          <TabsTrigger value="files">文件库</TabsTrigger>
        </TabsList>

        {/* Actions Tab */}
        <TabsContent value="actions" className="mt-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {QUICK_ACTIONS.filter((a) => visibleFeatureIds.includes(a.featureId)).map(
              (action) => {
                const Icon = ICON_MAP[action.icon] || Zap;
                return (
                  <button
                    key={action.featureId}
                    onClick={() =>
                      router.push(
                        `/features?feature=${action.featureId}&client_id=${clientId}`
                      )
                    }
                    className="flex items-start gap-3 p-4 rounded-lg border bg-white hover:bg-indigo-50 hover:border-indigo-200 transition text-left"
                  >
                    <div className="w-10 h-10 rounded-lg bg-indigo-100 flex items-center justify-center shrink-0">
                      <Icon className="w-5 h-5 text-indigo-600" />
                    </div>
                    <div>
                      <p className="font-medium text-sm text-gray-900">
                        {action.label}
                      </p>
                      <p className="text-xs text-gray-500 mt-0.5">
                        {action.description}
                      </p>
                    </div>
                  </button>
                );
              }
            )}
          </div>
          {visibleFeatureIds.length === 0 && (
            <div className="text-center py-8 text-gray-400">加载中...</div>
          )}
        </TabsContent>

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
                      <p className="font-medium text-sm">{getFeatureName(entry.feature_id)}</p>
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
          <div className="mb-4 flex justify-end">
            <Link href={`/vault?client=${encodeURIComponent(client.code_name)}`}>
              <Button variant="outline" size="sm">
                <FolderOpen className="w-4 h-4 mr-2" />
                查看完整文件树
              </Button>
            </Link>
          </div>
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
                          <li key={f} className="text-sm">
                            <button
                              className="text-indigo-600 hover:text-indigo-800 hover:underline flex items-center"
                              onClick={() => openFileViewer(label, f)}
                            >
                              <span className="mr-2">📄</span>
                              {f}
                            </button>
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

      {/* Vault File Viewer */}
      <VaultFileViewer
        path={viewerPath}
        open={viewerOpen}
        onOpenChange={setViewerOpen}
      />
    </div>
  );
}
