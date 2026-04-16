"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { StaffAssignmentPanel } from "@/components/staff-assignment-panel";
import { VaultFileViewer } from "@/components/vault-file-viewer";
import { JobFormModal } from "@/components/job-form-modal";
import { FeatureIcon } from "@/components/feature-icon";
import { getFeatureName } from "@/lib/feature-names";
import { FolderOpen } from "lucide-react";
import type { Client, Feature } from "@/types";

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

interface VaultFileEntry {
  name: string;
  path: string;
}

interface TimelineResponse {
  client: Client;
  timeline: TimelineEntry[];
  vault_files: Record<string, VaultFileEntry[]>;
  total_jobs: number;
  completed_jobs: number;
}

// Feature type from API (subset; full type lives in @/types)
interface FeatureItem {
  id: string;
  display_name: string;
  description: string;
  icon: string;
  category: string;
  is_destructive?: boolean;
}

export default function ClientDetailPage() {
  const params = useParams();
  const { user } = useAuth();
  const clientId = params.id as string;
  const [data, setData] = useState<TimelineResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [viewerPath, setViewerPath] = useState<string | null>(null);
  const [viewerOpen, setViewerOpen] = useState(false);

  // Features visible to this user (from API, includes all plan features)
  const [features, setFeatures] = useState<FeatureItem[]>([]);
  const [featuresLoaded, setFeaturesLoaded] = useState(false);

  // Job form modal state
  const [selectedFeature, setSelectedFeature] = useState<Feature | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  // Load timeline and features in parallel, only show page when both done
  useEffect(() => {
    if (!clientId) return;

    const loadTimeline = api
      .get<TimelineResponse>(`/clients/${clientId}/timeline`)
      .then(setData)
      .catch(() => {});

    const loadFeatures = api
      .get<{ features: FeatureItem[] }>("/features")
      .then((res) => {
        setFeatures(res.features);
        setFeaturesLoaded(true);
      })
      .catch(() => setFeaturesLoaded(true));

    Promise.all([loadTimeline, loadFeatures]).finally(() => setLoading(false));
  }, [clientId]);

  function openFileViewer(vaultPath: string) {
    setViewerPath(vaultPath);
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
          {!featuresLoaded ? (
            <div className="text-center py-8 text-gray-400">加载功能列表中...</div>
          ) : features.length === 0 ? (
            <div className="text-center py-8 text-gray-400">暂无可用功能</div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {features.map((feat) => {
                const danger = feat.is_destructive === true;
                return (
                  <button
                    key={feat.id}
                    onClick={() => {
                      setSelectedFeature(feat as unknown as Feature);
                      setModalOpen(true);
                    }}
                    className={
                      "flex items-start gap-3 p-4 rounded-lg border transition text-left " +
                      (danger
                        ? "bg-white border-red-300 hover:bg-red-50 hover:border-red-400"
                        : "bg-white hover:bg-indigo-50 hover:border-indigo-200")
                    }
                  >
                    <div
                      className={
                        "w-10 h-10 rounded-lg flex items-center justify-center shrink-0 " +
                        (danger ? "bg-red-100" : "bg-indigo-100")
                      }
                    >
                      <FeatureIcon
                        name={feat.icon || "wrench"}
                        className={"w-5 h-5 " + (danger ? "text-red-600" : "text-indigo-600")}
                      />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <p className="font-medium text-sm text-gray-900 truncate">
                          {feat.display_name}
                        </p>
                        {danger && (
                          <span className="shrink-0 text-[10px] px-1.5 py-0.5 rounded bg-red-100 text-red-700 font-medium">
                            ⚠️ 不可逆
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">
                        {feat.description}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
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
                          <li key={f.path} className="text-sm">
                            <button
                              className="text-indigo-600 hover:text-indigo-800 hover:underline flex items-center"
                              onClick={() => openFileViewer(f.path)}
                            >
                              <span className="mr-2">📄</span>
                              {f.name}
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

      {/* Job Form Modal — opens in-page, no navigation */}
      <JobFormModal
        feature={selectedFeature}
        open={modalOpen}
        onClose={() => {
          setModalOpen(false);
          setSelectedFeature(null);
        }}
        defaultClientId={clientId}
      />
    </div>
  );
}
