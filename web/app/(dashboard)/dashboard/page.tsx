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
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
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
            <CardTitle className="text-sm text-muted-foreground">完成率</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{data.completion_rate}%</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">Token 用量</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatTokens(token_usage.total_input_tokens + token_usage.total_output_tokens)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              费用 {formatCents(token_usage.total_cost_cents)}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">个案数</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{data.total_clients}</div>
            <p className="text-xs text-muted-foreground mt-1">
              待审核 {data.pending_reviews}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Usage Chart */}
      {daily && daily.breakdown.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">日度 Token 趋势</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={daily.breakdown}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 12 }}
                    tickFormatter={(v: string) => v.slice(5)}
                  />
                  <YAxis tick={{ fontSize: 12 }} tickFormatter={formatTokens} />
                  <Tooltip
                    formatter={(value, name) => [
                      formatTokens(Number(value)),
                      name === "input_tokens" ? "输入" : "输出",
                    ]}
                  />
                  <Line
                    type="monotone"
                    dataKey="input_tokens"
                    stroke="#6366f1"
                    strokeWidth={2}
                    dot={false}
                    name="input_tokens"
                  />
                  <Line
                    type="monotone"
                    dataKey="output_tokens"
                    stroke="#10b981"
                    strokeWidth={2}
                    dot={false}
                    name="output_tokens"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

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
