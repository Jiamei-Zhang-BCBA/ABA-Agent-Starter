"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getFeatureName } from "@/lib/feature-names";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";

interface DashboardData {
  total_clients: number;
  total_jobs_this_month: number;
  completion_rate: number;
  token_usage: {
    year_month: string;
    total_jobs: number;
    total_input_tokens: number;
    total_output_tokens: number;
    total_cost_cents: number;
  };
  recent_jobs: {
    id: string;
    feature_id: string;
    status: string;
    created_at: string | null;
  }[];
  pending_reviews: number;
}

interface DailyData {
  year_month: string;
  breakdown: {
    date: string;
    jobs: number;
    input_tokens: number;
    output_tokens: number;
    cost_cents: number;
  }[];
}

const STATUS_MAP: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  queued: { label: "排队中", variant: "secondary" },
  parsing: { label: "解析中", variant: "outline" },
  processing: { label: "处理中", variant: "outline" },
  pending_review: { label: "待审核", variant: "secondary" },
  approved: { label: "已审核", variant: "default" },
  delivered: { label: "已完成", variant: "default" },
  rejected: { label: "已退回", variant: "destructive" },
  failed: { label: "失败", variant: "destructive" },
};

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function formatCents(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [daily, setDaily] = useState<DailyData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<DashboardData>("/dashboard/overview"),
      api.get<DailyData>("/usage/daily"),
    ])
      .then(([overview, dailyData]) => {
        setData(overview);
        setDaily(dailyData);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="text-center py-12 text-gray-400">加载中...</div>;
  }

  if (!data) {
    return <div className="text-center py-12 text-gray-400">加载失败</div>;
  }

  const { token_usage } = data;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">概览</h1>
        <p className="text-muted-foreground mt-1">本月运营数据一览</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">个案数</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{data.total_clients}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">本月任务</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{data.total_jobs_this_month}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">待审核</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{data.pending_reviews}</div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Jobs */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">最近任务</CardTitle>
        </CardHeader>
        <CardContent>
          {data.recent_jobs.length === 0 ? (
            <p className="text-sm text-gray-400">暂无任务</p>
          ) : (
            <div className="space-y-2">
              {data.recent_jobs.map((job) => {
                const s = STATUS_MAP[job.status] || { label: job.status, variant: "secondary" as const };
                return (
                  <div
                    key={job.id}
                    className="flex items-center justify-between py-2 border-b last:border-0"
                  >
                    <div className="flex items-center space-x-3">
                      <span className="text-sm font-medium">
                        {getFeatureName(job.feature_id)}
                      </span>
                      <Badge variant={s.variant}>{s.label}</Badge>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {formatDate(job.created_at)}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
