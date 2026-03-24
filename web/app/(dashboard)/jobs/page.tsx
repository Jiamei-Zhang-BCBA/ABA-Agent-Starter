"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { MarkdownViewer } from "@/components/markdown-viewer";
import { MarkdownEditor } from "@/components/markdown-editor";
import type { Job, JobDetail, JobListResponse } from "@/types";

const STATUS_MAP: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  pending: { label: "等待中", variant: "secondary" },
  processing: { label: "处理中", variant: "outline" },
  delivered: { label: "已完成", variant: "default" },
  failed: { label: "失败", variant: "destructive" },
};

function formatTime(iso: string) {
  return new Date(iso).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [selectedJob, setSelectedJob] = useState<JobDetail | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const pageSize = 20;

  const fetchJobs = useCallback(() => {
    setLoading(true);
    api
      .get<JobListResponse>(`/jobs?skip=${(page - 1) * pageSize}&limit=${pageSize}`)
      .then((res) => {
        setJobs(res.jobs);
        setTotal(res.total);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [page]);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  async function openJobDetail(job: Job) {
    try {
      const detail = await api.get<JobDetail>(`/jobs/${job.id}`);
      setSelectedJob(detail);
      setEditing(false);
      setSheetOpen(true);
    } catch {
      // ignore
    }
  }

  function downloadMarkdown(content: string, jobId: string) {
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `job-${jobId}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">任务记录</h1>
        <p className="text-muted-foreground mt-1">查看所有已提交的任务</p>
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-400">加载中...</div>
      ) : jobs.length === 0 ? (
        <div className="text-center py-12 text-gray-400">暂无任务记录</div>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>功能</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>创建时间</TableHead>
                <TableHead>完成时间</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {jobs.map((job) => {
                const s = STATUS_MAP[job.status] || { label: job.status, variant: "secondary" as const };
                return (
                  <TableRow
                    key={job.id}
                    className="cursor-pointer hover:bg-gray-50"
                    onClick={() => openJobDetail(job)}
                  >
                    <TableCell className="font-medium">{job.feature_id}</TableCell>
                    <TableCell>
                      <Badge variant={s.variant}>{s.label}</Badge>
                    </TableCell>
                    <TableCell>{formatTime(job.created_at)}</TableCell>
                    <TableCell>{job.completed_at ? formatTime(job.completed_at) : "—"}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>

          {totalPages > 1 && (
            <div className="flex justify-center items-center space-x-4">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                上一页
              </Button>
              <span className="text-sm text-gray-500">
                第 {page} / {totalPages} 页
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                下一页
              </Button>
            </div>
          )}
        </>
      )}

      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent className="w-full sm:max-w-2xl overflow-y-auto">
          <SheetHeader>
            <SheetTitle>任务详情</SheetTitle>
          </SheetHeader>
          {selectedJob && (
            <div className="space-y-4 mt-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">功能：</span>
                  {selectedJob.feature_id}
                </div>
                <div>
                  <span className="text-muted-foreground">状态：</span>
                  {STATUS_MAP[selectedJob.status]?.label || selectedJob.status}
                </div>
                <div>
                  <span className="text-muted-foreground">创建时间：</span>
                  {formatTime(selectedJob.created_at)}
                </div>
                {selectedJob.completed_at && (
                  <div>
                    <span className="text-muted-foreground">完成时间：</span>
                    {formatTime(selectedJob.completed_at)}
                  </div>
                )}
              </div>

              {selectedJob.status === "delivered" && selectedJob.output_content && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="font-medium">输出内容</h3>
                    <div className="space-x-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          downloadMarkdown(selectedJob.output_content!, selectedJob.id)
                        }
                      >
                        下载 .md
                      </Button>
                      {!editing && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setEditing(true)}
                        >
                          编辑
                        </Button>
                      )}
                    </div>
                  </div>
                  {editing ? (
                    <MarkdownEditor
                      jobId={selectedJob.id}
                      initialContent={selectedJob.output_content}
                      onSave={(content) => {
                        setSelectedJob({ ...selectedJob, output_content: content });
                        setEditing(false);
                      }}
                      onCancel={() => setEditing(false)}
                    />
                  ) : (
                    <div className="border rounded-md p-4">
                      <MarkdownViewer content={selectedJob.output_content} />
                    </div>
                  )}
                </div>
              )}

              {selectedJob.status === "processing" && (
                <div className="text-center py-8 text-gray-400">
                  <div className="animate-spin w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full mx-auto mb-3" />
                  处理中...
                </div>
              )}

              {selectedJob.status === "failed" && selectedJob.error_message && (
                <div className="bg-red-50 border border-red-200 rounded-md p-4 text-red-700 text-sm">
                  {selectedJob.error_message}
                </div>
              )}
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
