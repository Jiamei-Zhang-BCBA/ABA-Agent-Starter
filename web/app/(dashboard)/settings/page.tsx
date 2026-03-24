"use client";

import { useState } from "react";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

const ROLE_LABELS: Record<string, string> = {
  org_admin: "管理员",
  bcba: "BCBA",
  teacher: "老师",
  parent: "家长",
};

export default function SettingsPage() {
  const { user } = useAuth();
  const [email, setEmail] = useState("");
  const [resetSent, setResetSent] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handlePasswordReset() {
    if (!user) return;
    setLoading(true);
    try {
      await api.post("/users/password-reset", { email: user.email });
      setResetSent(true);
      toast.success("重置邮件已发送");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "发送失败");
    } finally {
      setLoading(false);
    }
  }

  if (!user) return null;

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">账户设置</h1>
        <p className="text-muted-foreground mt-1">管理您的账户信息</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>个人信息</CardTitle>
          <CardDescription>您的账户基本信息</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label className="text-muted-foreground">姓名</Label>
              <p className="font-medium">{user.name}</p>
            </div>
            <div>
              <Label className="text-muted-foreground">邮箱</Label>
              <p className="font-medium">{user.email}</p>
            </div>
            <div>
              <Label className="text-muted-foreground">角色</Label>
              <div className="mt-1">
                <Badge>{ROLE_LABELS[user.role] || user.role}</Badge>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>修改密码</CardTitle>
          <CardDescription>通过邮箱验证来重置密码</CardDescription>
        </CardHeader>
        <CardContent>
          {resetSent ? (
            <p className="text-sm text-muted-foreground">
              重置链接已发送至 {user.email}，请检查邮箱并按照指引操作。
            </p>
          ) : (
            <Button onClick={handlePasswordReset} disabled={loading}>
              {loading ? "发送中..." : "发送密码重置邮件"}
            </Button>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
