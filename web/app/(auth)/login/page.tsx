"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { RefreshCw } from "lucide-react";
import type { TokenResponse } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

interface AuthConfig {
  registration_enabled: boolean;
  captcha_enabled: boolean;
}

interface CaptchaData {
  captcha_id: string;
  question: string;
}

export default function LoginPage() {
  const router = useRouter();
  const { setAuth, setUser, logout } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Auth config
  const [config, setConfig] = useState<AuthConfig | null>(null);

  // Captcha state
  const [captcha, setCaptcha] = useState<CaptchaData | null>(null);
  const [captchaAnswer, setCaptchaAnswer] = useState("");

  // Clear stale tokens when landing on login page
  useEffect(() => {
    logout();
  }, [logout]);

  // Fetch auth config
  useEffect(() => {
    fetch(`${API_BASE}/admin/auth-config`)
      .then((r) => r.json())
      .then(setConfig)
      .catch(() => setConfig({ registration_enabled: false, captcha_enabled: false }));
  }, []);

  const loadCaptcha = useCallback(() => {
    setCaptchaAnswer("");
    fetch(`${API_BASE}/auth/captcha`)
      .then((r) => r.json())
      .then(setCaptcha)
      .catch(() => setCaptcha(null));
  }, []);

  // Load captcha when config says it's enabled
  useEffect(() => {
    if (config?.captcha_enabled) {
      loadCaptcha();
    }
  }, [config, loadCaptcha]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const body: Record<string, string> = { email, password };
      if (config?.captcha_enabled && captcha) {
        body.captcha_id = captcha.captcha_id;
        body.captcha_answer = captchaAnswer;
      }

      const tokens = await api.post<TokenResponse>("/auth/login", body);
      setAuth(tokens.access_token, tokens.refresh_token);

      const meRes = await fetch(`${API_BASE}/auth/me`, {
        headers: { Authorization: `Bearer ${tokens.access_token}` },
      });
      if (meRes.ok) {
        const user = await meRes.json();
        setUser(user);
      }

      router.push("/clients");
    } catch (err) {
      // Refresh captcha on any login failure
      if (config?.captcha_enabled) loadCaptcha();

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

          {/* CAPTCHA */}
          {config?.captcha_enabled && captcha && (
            <div className="space-y-2">
              <Label htmlFor="captcha">验证码</Label>
              <div className="flex items-center gap-3">
                <div className="flex-1 bg-gray-50 border rounded-md px-3 py-2 text-center font-mono text-lg select-none">
                  {captcha.question}
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={loadCaptcha}
                  title="换一道题"
                >
                  <RefreshCw className="w-4 h-4" />
                </Button>
              </div>
              <Input
                id="captcha"
                type="text"
                inputMode="numeric"
                value={captchaAnswer}
                onChange={(e) => setCaptchaAnswer(e.target.value)}
                placeholder="请输入计算结果"
                required
              />
            </div>
          )}

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
          {config?.registration_enabled && (
            <p>
              还没有账号？{" "}
              <Link href="/register" className="text-indigo-600 hover:underline">
                注册组织
              </Link>
            </p>
          )}
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
