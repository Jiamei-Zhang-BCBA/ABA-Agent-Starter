"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Plus } from "lucide-react";
import type { Client, Staff } from "@/types";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("zh-CN");
}

export default function ClientsPage() {
  const { user } = useAuth();
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [staff, setStaff] = useState<Staff[]>([]);
  const [filterTeacherId, setFilterTeacherId] = useState("all");

  const isSupervisor = user?.role === "org_admin" || user?.role === "bcba";

  useEffect(() => {
    if (isSupervisor) {
      api
        .get<{ staff: Staff[] }>("/staff")
        .then((res) => setStaff(res.staff.filter((s) => s.role === "teacher")))
        .catch(() => {});
    }
  }, [isSupervisor]);

  useEffect(() => {
    setLoading(true);
    const params = filterTeacherId !== "all" ? `?teacher_id=${filterTeacherId}` : "";
    api
      .get<{ clients: Client[] }>(`/clients${params}`)
      .then((res) => setClients(res.clients))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [filterTeacherId]);

  if (loading) {
    return <div className="text-center py-12 text-gray-400">加载中...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">个案档案</h1>
          <p className="text-muted-foreground mt-1">查看和管理个案信息</p>
        </div>

        {isSupervisor && staff.length > 0 && (
          <div className="flex items-center space-x-2">
            <span className="text-sm text-muted-foreground">按老师筛选：</span>
            <Select
              value={filterTeacherId}
              onValueChange={(v) => v && setFilterTeacherId(v)}
            >
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部</SelectItem>
                {staff.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {clients.map((client) => (
            <Link key={client.id} href={`/clients/${client.id}`}>
              <Card className="hover:shadow-md transition-shadow cursor-pointer">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">{client.code_name}</CardTitle>
                    <Badge variant={client.status === "active" ? "default" : "secondary"}>
                      {client.status === "active" ? "活跃" : client.status}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="text-sm text-muted-foreground space-y-1">
                    <p>别名：{client.display_alias}</p>
                    <p>创建：{formatDate(client.created_at)}</p>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}

          {/* 新建个案卡片 */}
          {isSupervisor && (
            <Link href="/features?feature=intake">
              <Card className="hover:shadow-md transition-shadow cursor-pointer border-dashed border-2 border-gray-300 hover:border-indigo-400">
                <div className="flex flex-col items-center justify-center h-full py-8">
                  <div className="w-12 h-12 rounded-full bg-indigo-50 flex items-center justify-center mb-3">
                    <Plus className="w-6 h-6 text-indigo-500" />
                  </div>
                  <p className="font-medium text-gray-600">新建个案</p>
                  <p className="text-xs text-gray-400 mt-1">发起初访建档流程</p>
                </div>
              </Card>
            </Link>
          )}
        </div>
    </div>
  );
}
