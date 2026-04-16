"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Building2, Users, FolderKanban, Plus } from "lucide-react";

interface TenantInfo {
  id: string;
  name: string;
  plan_name: string | null;
  user_count: number;
  client_count: number;
}

export default function AdminPage() {
  const { user } = useAuth();
  const [tenants, setTenants] = useState<TenantInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Create tenant dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({
    org_name: "",
    admin_name: "",
    admin_email: "",
    admin_password: "",
    plan_name: "starter",
  });
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState("");
  const [createSuccess, setCreateSuccess] = useState("");

  function loadTenants() {
    setLoading(true);
    api
      .get<{ tenants: TenantInfo[] }>("/admin/tenants")
      .then((res) => {
        setTenants(res.tenants);
        setError("");
      })
      .catch((e) => {
        setError(e instanceof ApiError ? e.detail : "加载失败");
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadTenants();
  }, []);

  async function handleCreateTenant(e: React.FormEvent) {
    e.preventDefault();
    setCreateLoading(true);
    setCreateError("");
    setCreateSuccess("");

    try {
      await api.post("/admin/tenants", createForm);
      setCreateSuccess(`组织 "${createForm.org_name}" 创建成功`);
      setCreateForm({
        org_name: "",
        admin_name: "",
        admin_email: "",
        admin_password: "",
        plan_name: "starter",
      });
      loadTenants();
    } catch (e) {
      setCreateError(e instanceof ApiError ? e.detail : "创建失败");
    } finally {
      setCreateLoading(false);
    }
  }

  async function updatePlan(tenantId: string, planName: string) {
    try {
      await api.patch(`/admin/tenants/${tenantId}/plan`, { plan_name: planName });
      loadTenants();
    } catch (e) {
      alert(e instanceof ApiError ? e.detail : "更新失败");
    }
  }

  if (error && tenants.length === 0) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">系统管理</h1>
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
        <p className="text-sm text-gray-500">
          需要超级管理员权限。请确认你的邮箱在 SUPER_ADMIN_EMAILS 配置中。
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">系统管理</h1>
          <p className="text-muted-foreground mt-1">
            管理组织、用户和系统配置（超级管理员）
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="w-4 h-4 mr-2" />
          新建组织
        </Button>
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-400">加载中...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {tenants.map((t) => (
            <Card key={t.id}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg flex items-center gap-2">
                    <Building2 className="w-5 h-5 text-gray-400" />
                    {t.name}
                  </CardTitle>
                  <Badge variant="secondary">{t.plan_name || "无套餐"}</Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center gap-4 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Users className="w-4 h-4" />
                    {t.user_count} 用户
                  </span>
                  <span className="flex items-center gap-1">
                    <FolderKanban className="w-4 h-4" />
                    {t.client_count} 个案
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">套餐：</span>
                  <Select
                    value={t.plan_name || "starter"}
                    onValueChange={(v) => v && updatePlan(t.id, v)}
                  >
                    <SelectTrigger className="h-8 text-xs w-28">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="starter">基础版</SelectItem>
                      <SelectItem value="professional">专业版</SelectItem>
                      <SelectItem value="enterprise">旗舰版</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <p className="text-xs text-gray-400 font-mono truncate">{t.id}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create Tenant Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>新建组织</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreateTenant} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="org_name">组织名称</Label>
              <Input
                id="org_name"
                value={createForm.org_name}
                onChange={(e) =>
                  setCreateForm({ ...createForm, org_name: e.target.value })
                }
                placeholder="如：阳光星星ABA中心"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="admin_name">管理员姓名</Label>
              <Input
                id="admin_name"
                value={createForm.admin_name}
                onChange={(e) =>
                  setCreateForm({ ...createForm, admin_name: e.target.value })
                }
                placeholder="如：张老师"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="admin_email">管理员邮箱</Label>
              <Input
                id="admin_email"
                type="email"
                value={createForm.admin_email}
                onChange={(e) =>
                  setCreateForm({ ...createForm, admin_email: e.target.value })
                }
                placeholder="admin@example.com"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="admin_password">初始密码</Label>
              <Input
                id="admin_password"
                type="password"
                value={createForm.admin_password}
                onChange={(e) =>
                  setCreateForm({
                    ...createForm,
                    admin_password: e.target.value,
                  })
                }
                placeholder="至少6位"
                required
                minLength={6}
              />
            </div>
            <div className="space-y-2">
              <Label>订阅套餐</Label>
              <Select
                value={createForm.plan_name}
                onValueChange={(v) =>
                  v && setCreateForm({ ...createForm, plan_name: v })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="starter">基础版</SelectItem>
                  <SelectItem value="professional">专业版</SelectItem>
                  <SelectItem value="enterprise">旗舰版</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {createError && (
              <Alert variant="destructive">
                <AlertDescription>{createError}</AlertDescription>
              </Alert>
            )}
            {createSuccess && (
              <Alert>
                <AlertDescription className="text-green-700">
                  {createSuccess}
                </AlertDescription>
              </Alert>
            )}

            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setCreateOpen(false)}
              >
                取消
              </Button>
              <Button type="submit" disabled={createLoading}>
                {createLoading ? "创建中..." : "创建组织"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
