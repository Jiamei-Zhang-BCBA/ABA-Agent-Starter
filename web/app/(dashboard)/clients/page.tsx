"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Client } from "@/types";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("zh-CN");
}

export default function ClientsPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<{ clients: Client[] }>("/clients")
      .then((res) => setClients(res.clients))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="text-center py-12 text-gray-400">加载中...</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">个案档案</h1>
        <p className="text-muted-foreground mt-1">查看和管理个案信息</p>
      </div>

      {clients.length === 0 ? (
        <div className="text-center py-12 text-gray-400">暂无个案</div>
      ) : (
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
        </div>
      )}
    </div>
  );
}
