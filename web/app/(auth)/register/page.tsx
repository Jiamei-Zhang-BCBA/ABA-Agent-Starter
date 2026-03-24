"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import type { RegisterResponse } from "@/types";

export default function RegisterPage() {
  const router = useRouter();
  const { setAuth } = useAuth();
  const [form, setForm] = useState({
    org_name: "",
    admin_name: "",
    admin_email: "",
    admin_password: "",
    confirm_password: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function updateField(field: string, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (form.admin_password !== form.confirm_password) {
      setError("两次输入的密码不一致");
      return;
    }

    if (form.admin_password.length < 8) {
      setError("密码至少需要 8 个字符");
      return;
    }

    setLoading(true);

    try {
      const res = await api.post<RegisterResponse>("/users/register", {
        org_name: form.org_name,
        admin_name: form.admin_name,
        admin_email: form.admin_email,
        admin_password: form.admin_password,
      });
      setAuth(res.access_token, res.refresh_token);
      router.push("/features");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else if (err instanceof Error) {
        setError(`注册失败: ${err.message}`);
      } else {
        setError("注册失败，请检查网络连接");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader className="text-center">
        <CardTitle className="text-2xl">注册组织</CardTitle>
        <CardDescription>创建您的 ABA 督导系统账户</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="org_name">机构名称</Label>
            <Input
              id="org_name"
              value={form.org_name}
              onChange={(e) => updateField("org_name", e.target.value)}
              placeholder="请输入机构名称"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="admin_name">管理员姓名</Label>
            <Input
              id="admin_name"
              value={form.admin_name}
              onChange={(e) => updateField("admin_name", e.target.value)}
              placeholder="请输入姓名"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="admin_email">管理员邮箱</Label>
            <Input
              id="admin_email"
              type="email"
              value={form.admin_email}
              onChange={(e) => updateField("admin_email", e.target.value)}
              placeholder="请输入邮箱"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="admin_password">密码</Label>
            <Input
              id="admin_password"
              type="password"
              value={form.admin_password}
              onChange={(e) => updateField("admin_password", e.target.value)}
              placeholder="至少 8 个字符"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="confirm_password">确认密码</Label>
            <Input
              id="confirm_password"
              type="password"
              value={form.confirm_password}
              onChange={(e) => updateField("confirm_password", e.target.value)}
              placeholder="再次输入密码"
              required
            />
          </div>
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "注册中..." : "注 册"}
          </Button>
        </form>
        <div className="mt-6 text-center text-sm text-muted-foreground">
          已有账号？{" "}
          <Link href="/login" className="text-indigo-600 hover:underline">
            登录
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
