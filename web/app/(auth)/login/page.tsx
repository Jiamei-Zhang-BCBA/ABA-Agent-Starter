"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import type { TokenResponse, User } from "@/types";

export default function LoginPage() {
  const router = useRouter();
  const { setAuth, setUser, logout } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Clear stale tokens when landing on login page
  useEffect(() => {
    logout();
  }, [logout]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const tokens = await api.post<TokenResponse>("/auth/login", { email, password });
      setAuth(tokens.access_token, tokens.refresh_token);

      // Fetch user profile with explicit token to avoid store timing issues
      const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
      const meRes = await fetch(`${API_BASE}/auth/me`, {
        headers: { Authorization: `Bearer ${tokens.access_token}` },
      });
      if (meRes.ok) {
        const user = await meRes.json();
        setUser(user);
      }

      router.push("/features");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else if (err instanceof Error) {
        setError(`登录失败: ${err.message}`);
      } else {
        setError("登录失败，请检查网络连接");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader className="text-center">
        <div className="w-16 h-16 bg-indigo-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
          <span className="text-2xl">📘</span>
        </div>
        <CardTitle className="text-2xl">ABA 临床督导系统</CardTitle>
        <CardDescription>智能化临床督导 SaaS 平台</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">邮箱</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="请输入邮箱"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">密码</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="请输入密码"
              required
            />
          </div>
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "登录中..." : "登 录"}
          </Button>
        </form>
        <div className="mt-6 text-center text-sm text-muted-foreground space-y-1">
          <p>
            还没有账号？{" "}
            <Link href="/register" className="text-indigo-600 hover:underline">
              注册组织
            </Link>
          </p>
          <p>
            <Link href="/forgot-password" className="text-indigo-600 hover:underline">
              忘记密码？
            </Link>
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
