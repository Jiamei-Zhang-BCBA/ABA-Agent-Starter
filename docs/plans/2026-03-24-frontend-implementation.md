# Frontend Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a complete Next.js frontend for the ABA Clinical Supervision SaaS, replacing the existing Alpine.js SPA.

**Architecture:** Independent `web/` directory using Next.js 15 App Router. Route groups split public auth pages from authenticated dashboard pages. All API calls are client-side via a unified fetch wrapper with JWT token management.

**Tech Stack:** Next.js 15, React 19, TypeScript, Tailwind CSS 4, shadcn/ui, Zustand, react-hook-form, zod, react-markdown, lucide-react

---

### Task 1: Scaffold Next.js project

**Files:**
- Create: `web/` directory with Next.js boilerplate

**Step 1: Create Next.js project**

Run:
```bash
cd D:/OneDrive/wxob/ABA-Agent-Starter
npx create-next-app@latest web --typescript --tailwind --eslint --app --src-dir=false --import-alias="@/*" --use-npm
```
Select defaults when prompted.

**Step 2: Install dependencies**

Run:
```bash
cd D:/OneDrive/wxob/ABA-Agent-Starter/web
npm install zustand react-hook-form @hookform/resolvers zod react-markdown remark-gfm
```

**Step 3: Initialize shadcn/ui**

Run:
```bash
cd D:/OneDrive/wxob/ABA-Agent-Starter/web
npx shadcn@latest init -d
```

**Step 4: Add shadcn components**

Run:
```bash
npx shadcn@latest add button card dialog input label select textarea tabs badge table dropdown-menu toast separator avatar alert sheet
```

**Step 5: Verify dev server starts**

Run:
```bash
cd D:/OneDrive/wxob/ABA-Agent-Starter/web && npm run dev
```
Expected: Server starts on http://localhost:3000

**Step 6: Update API CORS to allow frontend origin**

Modify: `api/app/config.py:34`

Change:
```python
cors_origins: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000"]
```
To:
```python
cors_origins: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:3000"]
```

**Step 7: Commit**

```bash
git add web/ api/app/config.py
git commit -m "feat: scaffold Next.js frontend with shadcn/ui"
```

---

### Task 2: API client and auth store

**Files:**
- Create: `web/lib/api.ts`
- Create: `web/lib/auth.ts`
- Create: `web/lib/utils.ts` (may already exist from shadcn init)
- Create: `web/types/index.ts`

**Step 1: Create TypeScript types matching backend schemas**

Create `web/types/index.ts`:
```typescript
// Auth
export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface User {
  id: string;
  tenant_id: string;
  role: "org_admin" | "bcba" | "teacher" | "parent";
  name: string;
  email: string;
}

// Registration
export interface RegisterRequest {
  org_name: string;
  admin_name: string;
  admin_email: string;
  admin_password: string;
  plan_name?: string;
}

export interface RegisterResponse {
  tenant_id: string;
  user_id: string;
  email: string;
  access_token: string;
  refresh_token: string;
}

// Invitation
export interface InvitationCreateRequest {
  email: string;
  role: "bcba" | "teacher" | "parent";
}

export interface InvitationResponse {
  id: string;
  email: string;
  role: string;
  token: string;
  expires_at: string;
}

export interface InvitationAcceptRequest {
  token: string;
  name: string;
  password: string;
}

// Password Reset
export interface PasswordResetRequest {
  email: string;
}

export interface PasswordResetConfirm {
  token: string;
  new_password: string;
}

// Users
export interface UserDetail {
  id: string;
  tenant_id: string;
  role: string;
  name: string;
  email: string;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface UserListResponse {
  users: UserDetail[];
  total: number;
}

export interface UserUpdateRequest {
  name?: string;
  role?: string;
  is_active?: boolean;
}

// Features
export interface FormField {
  name: string;
  label: string;
  type: "text" | "number" | "textarea" | "file" | "select_client" | "select_staff";
  required: boolean;
  accept?: string[];
  options?: { value: string; label: string }[];
}

export interface Feature {
  id: string;
  display_name: string;
  description: string;
  icon: string;
  category: string;
  form_schema: { fields: FormField[] };
  output_template: string;
}

export interface FeatureListResponse {
  features: Feature[];
}

// Jobs
export interface Job {
  id: string;
  tenant_id: string;
  user_id: string;
  client_id: string | null;
  feature_id: string;
  status: string;
  created_at: string;
  completed_at: string | null;
}

export interface JobDetail extends Job {
  form_data_json: Record<string, unknown>;
  output_content: string | null;
  error_message: string | null;
  input_tokens: number;
  output_tokens: number;
}

export interface JobListResponse {
  jobs: Job[];
  total: number;
}

// Clients
export interface Client {
  id: string;
  tenant_id: string;
  code_name: string;
  display_alias: string;
  status: string;
  created_at: string;
}

export interface Staff {
  id: string;
  name: string;
  role: string;
}

// Reviews
export interface Review {
  id: string;
  job_id: string;
  reviewer_id: string | null;
  output_content: string;
  modified_content: string | null;
  status: string;
  comments: string | null;
  created_at: string;
  reviewed_at: string | null;
}
```

**Step 2: Create Zustand auth store**

Create `web/lib/auth.ts`:
```typescript
import { create } from "zustand";
import type { User } from "@/types";

interface AuthState {
  token: string | null;
  refreshToken: string | null;
  user: User | null;
  setAuth: (token: string, refreshToken: string) => void;
  setUser: (user: User) => void;
  logout: () => void;
  hydrate: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  token: null,
  refreshToken: null,
  user: null,

  setAuth: (token, refreshToken) => {
    localStorage.setItem("aba_token", token);
    localStorage.setItem("aba_refresh_token", refreshToken);
    set({ token, refreshToken });
  },

  setUser: (user) => set({ user }),

  logout: () => {
    localStorage.removeItem("aba_token");
    localStorage.removeItem("aba_refresh_token");
    set({ token: null, refreshToken: null, user: null });
  },

  hydrate: () => {
    const token = localStorage.getItem("aba_token");
    const refreshToken = localStorage.getItem("aba_refresh_token");
    if (token) {
      set({ token, refreshToken });
    }
  },
}));
```

**Step 3: Create API fetch wrapper**

Create `web/lib/api.ts`:
```typescript
import { useAuth } from "./auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const { token, logout } = useAuth.getState();

  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  // Don't set Content-Type for FormData (browser sets multipart boundary)
  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    logout();
    window.location.href = "/login";
    throw new ApiError(401, "登录已过期");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "请求失败" }));
    throw new ApiError(res.status, body.detail || "请求失败");
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      body: body instanceof FormData ? body : JSON.stringify(body),
    }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  delete: <T>(path: string) =>
    request<T>(path, { method: "DELETE" }),
};

export { ApiError };
```

**Step 4: Create `.env.local`**

Create `web/.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

**Step 5: Verify imports compile**

Run:
```bash
cd D:/OneDrive/wxob/ABA-Agent-Starter/web && npm run build
```
Expected: Build succeeds (pages are default Next.js pages)

**Step 6: Commit**

```bash
git add web/lib/ web/types/ web/.env.local
git commit -m "feat: add API client, auth store, and TypeScript types"
```

---

### Task 3: Root layout and auth layout

**Files:**
- Modify: `web/app/layout.tsx`
- Create: `web/app/(auth)/layout.tsx`
- Create: `web/components/providers.tsx`

**Step 1: Create client-side providers wrapper**

Create `web/components/providers.tsx`:
```typescript
"use client";

import { useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { Toaster } from "@/components/ui/toaster";

export function Providers({ children }: { children: React.ReactNode }) {
  const hydrate = useAuth((s) => s.hydrate);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  return (
    <>
      {children}
      <Toaster />
    </>
  );
}
```

**Step 2: Update root layout**

Modify `web/app/layout.tsx`:
```typescript
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "ABA 临床督导系统",
  description: "智能化临床督导 SaaS 平台",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className={inter.className}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

**Step 3: Create auth layout (centered card)**

Create `web/app/(auth)/layout.tsx`:
```typescript
export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="w-full max-w-md mx-4">{children}</div>
    </div>
  );
}
```

**Step 4: Commit**

```bash
git add web/app/ web/components/providers.tsx
git commit -m "feat: add root layout, auth layout, and providers"
```

---

### Task 4: Login page

**Files:**
- Create: `web/app/(auth)/login/page.tsx`

**Step 1: Create login page**

Create `web/app/(auth)/login/page.tsx`:
```typescript
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
import type { TokenResponse, User } from "@/types";

export default function LoginPage() {
  const router = useRouter();
  const { setAuth, setUser } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const tokens = await api.post<TokenResponse>("/auth/login", { email, password });
      setAuth(tokens.access_token, tokens.refresh_token);

      const user = await api.get<User>("/auth/me");
      setUser(user);

      router.push("/features");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "登录失败");
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
```

**Step 2: Verify page renders**

Run: `npm run dev`, visit http://localhost:3000/login
Expected: Login card form renders

**Step 3: Commit**

```bash
git add web/app/\(auth\)/login/
git commit -m "feat: add login page"
```

---

### Task 5: Register, invite accept, and password reset pages

**Files:**
- Create: `web/app/(auth)/register/page.tsx`
- Create: `web/app/(auth)/invite/page.tsx`
- Create: `web/app/(auth)/forgot-password/page.tsx`
- Create: `web/app/(auth)/reset-password/page.tsx`

**Step 1: Create register page**

Create `web/app/(auth)/register/page.tsx` — form with: org_name, admin_name, admin_email, admin_password, confirm_password. On success, auto-login and redirect to `/features`.

**Step 2: Create invite accept page**

Create `web/app/(auth)/invite/page.tsx` — reads `token` from URL search params, form with: name, password. Calls `POST /users/invite/accept`.

**Step 3: Create forgot password page**

Create `web/app/(auth)/forgot-password/page.tsx` — email input, calls `POST /users/password-reset`, shows success message.

**Step 4: Create reset password page**

Create `web/app/(auth)/reset-password/page.tsx` — reads `token` from URL, new_password + confirm, calls `POST /users/password-reset/confirm`.

**Step 5: Verify all pages render**

Visit each route in browser.

**Step 6: Commit**

```bash
git add web/app/\(auth\)/
git commit -m "feat: add register, invite, forgot-password, and reset-password pages"
```

---

### Task 6: Dashboard layout with navigation

**Files:**
- Create: `web/app/(dashboard)/layout.tsx`
- Create: `web/components/nav-bar.tsx`
- Create: `web/lib/hooks.ts`

**Step 1: Create auth guard hook**

Create `web/lib/hooks.ts`:
```typescript
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "./auth";
import { api } from "./api";
import type { User } from "@/types";

export function useRequireAuth() {
  const router = useRouter();
  const { token, user, setUser, hydrate } = useAuth();

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    if (!token) {
      router.push("/login");
      return;
    }
    if (!user) {
      api.get<User>("/auth/me").then(setUser).catch(() => {
        router.push("/login");
      });
    }
  }, [token, user, router, setUser]);

  return { user, token };
}

export function useRequireRole(...roles: string[]) {
  const { user } = useRequireAuth();

  useEffect(() => {
    if (user && !roles.includes(user.role)) {
      window.location.href = "/features";
    }
  }, [user, roles]);

  return { user };
}
```

**Step 2: Create navigation bar**

Create `web/components/nav-bar.tsx`:
```typescript
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const ROLE_LABELS: Record<string, string> = {
  org_admin: "管理员",
  bcba: "BCBA",
  teacher: "老师",
  parent: "家长",
};

interface NavItem {
  href: string;
  label: string;
  roles?: string[]; // if set, only these roles see this tab
}

const NAV_ITEMS: NavItem[] = [
  { href: "/features", label: "功能中心" },
  { href: "/jobs", label: "任务记录" },
  { href: "/clients", label: "个案档案" },
  { href: "/reviews", label: "审核队列", roles: ["org_admin", "bcba"] },
  { href: "/users", label: "用户管理", roles: ["org_admin"] },
];

export function NavBar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  if (!user) return null;

  const visibleItems = NAV_ITEMS.filter(
    (item) => !item.roles || item.roles.includes(user.role),
  );

  return (
    <nav className="bg-white shadow-sm border-b sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-14 items-center">
          <div className="flex items-center space-x-3">
            <span className="text-xl">📘</span>
            <span className="font-bold text-gray-800">ABA 督导系统</span>
          </div>
          <div className="flex items-center space-x-1">
            {visibleItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`px-3 py-4 text-sm font-medium transition ${
                  pathname.startsWith(item.href)
                    ? "text-indigo-600 border-b-2 border-indigo-600"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </div>
          <div className="flex items-center space-x-3">
            <span className="text-sm text-gray-600">{user.name}</span>
            <Badge variant="secondary">{ROLE_LABELS[user.role] || user.role}</Badge>
            <Link href="/settings" className="text-sm text-gray-500 hover:text-gray-700">
              设置
            </Link>
            <Button variant="ghost" size="sm" onClick={logout}>
              退出
            </Button>
          </div>
        </div>
      </div>
    </nav>
  );
}
```

**Step 3: Create dashboard layout**

Create `web/app/(dashboard)/layout.tsx`:
```typescript
"use client";

import { NavBar } from "@/components/nav-bar";
import { useRequireAuth } from "@/lib/hooks";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user } = useRequireAuth();

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-400">加载中...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {children}
      </div>
    </div>
  );
}
```

**Step 4: Commit**

```bash
git add web/app/\(dashboard\)/ web/components/nav-bar.tsx web/lib/hooks.ts
git commit -m "feat: add dashboard layout with nav bar and auth guard"
```

---

### Task 7: Features page + job submission modal

**Files:**
- Create: `web/app/(dashboard)/features/page.tsx`
- Create: `web/components/feature-card.tsx`
- Create: `web/components/job-form-modal.tsx`

**Step 1: Create feature card component**

Create `web/components/feature-card.tsx` — displays icon, name, description, category badge. onClick triggers modal.

**Step 2: Create dynamic job form modal**

Create `web/components/job-form-modal.tsx` — Dialog component that:
- Fetches `GET /features/{id}/schema` on open
- Dynamically renders form fields based on `form_schema.fields` using react-hook-form
- For `select_client`: fetches `GET /clients` for dropdown options
- For `select_staff`: fetches `GET /staff` for dropdown options
- For `file`: renders file input with accept filter
- Submits as `FormData` to `POST /jobs`
- Shows toast on success, closes modal

**Step 3: Create features page**

Create `web/app/(dashboard)/features/page.tsx` — fetches `GET /features`, renders category filter tabs + card grid + modal.

**Step 4: Commit**

```bash
git add web/app/\(dashboard\)/features/ web/components/feature-card.tsx web/components/job-form-modal.tsx
git commit -m "feat: add features page with dynamic job submission form"
```

---

### Task 8: Jobs page with output viewer/editor

**Files:**
- Create: `web/app/(dashboard)/jobs/page.tsx`
- Create: `web/components/markdown-viewer.tsx`
- Create: `web/components/markdown-editor.tsx`

**Step 1: Create markdown viewer**

Create `web/components/markdown-viewer.tsx` — wraps `react-markdown` with `remark-gfm`, styled with prose classes.

**Step 2: Create markdown editor**

Create `web/components/markdown-editor.tsx` — textarea with preview toggle, save/cancel buttons. Calls `PATCH /jobs/{id}/output`.

**Step 3: Create jobs page**

Create `web/app/(dashboard)/jobs/page.tsx`:
- Fetches `GET /jobs` with pagination
- Table with columns: feature name, status badge, created time
- Click row → Sheet (side panel) with job detail
- Status-dependent content: delivered → markdown viewer + edit button, processing → spinner, failed → error message
- Download .md button for delivered jobs

**Step 4: Commit**

```bash
git add web/app/\(dashboard\)/jobs/ web/components/markdown-viewer.tsx web/components/markdown-editor.tsx
git commit -m "feat: add jobs page with markdown output viewer and editor"
```

---

### Task 9: Clients page with timeline

**Files:**
- Create: `web/app/(dashboard)/clients/page.tsx`
- Create: `web/app/(dashboard)/clients/[id]/page.tsx`

**Step 1: Create clients list page**

Create `web/app/(dashboard)/clients/page.tsx` — card grid listing clients with code_name, display_alias, status badge, created date. Click → navigate to `/clients/[id]`.

**Step 2: Create client timeline page**

Create `web/app/(dashboard)/clients/[id]/page.tsx`:
- Fetches `GET /clients/{id}` for header info
- Fetches `GET /clients/{id}/timeline` for job history
- Displays timeline view: chronological list of jobs with status dots
- Back button to `/clients`

**Step 3: Commit**

```bash
git add web/app/\(dashboard\)/clients/
git commit -m "feat: add clients list and timeline detail pages"
```

---

### Task 10: Reviews page

**Files:**
- Create: `web/app/(dashboard)/reviews/page.tsx`
- Create: `web/components/review-card.tsx`

**Step 1: Create review card component**

Create `web/components/review-card.tsx` — shows output preview (truncated markdown), approve/reject buttons. Approve opens dialog for optional modified content. Reject opens dialog requiring comments.

**Step 2: Create reviews page**

Create `web/app/(dashboard)/reviews/page.tsx`:
- Role guard: only `org_admin` and `bcba`
- Fetches `GET /reviews`
- Renders review cards
- Calls `POST /reviews/{id}/approve` or `POST /reviews/{id}/reject`
- Refreshes list after action

**Step 3: Commit**

```bash
git add web/app/\(dashboard\)/reviews/ web/components/review-card.tsx
git commit -m "feat: add review queue page with approve/reject actions"
```

---

### Task 11: Users management page

**Files:**
- Create: `web/app/(dashboard)/users/page.tsx`

**Step 1: Create users page**

Create `web/app/(dashboard)/users/page.tsx`:
- Role guard: only `org_admin`
- Fetches `GET /users`
- Table: name, email, role, status, last login, actions
- Invite button → Dialog (email + role dropdown) → `POST /users/invite` → shows token/link
- Role change → inline Select → `PATCH /users/{id}` with `{ role }`
- Deactivate → confirm Dialog → `DELETE /users/{id}`
- Toast feedback for all actions

**Step 2: Commit**

```bash
git add web/app/\(dashboard\)/users/
git commit -m "feat: add user management page with invite and role management"
```

---

### Task 12: Settings page

**Files:**
- Create: `web/app/(dashboard)/settings/page.tsx`

**Step 1: Create settings page**

Create `web/app/(dashboard)/settings/page.tsx`:
- Displays current user info (name, email, role — read-only)
- Change password form: current password not needed (uses reset token flow internally), just new_password + confirm
- Actually calls `POST /users/password-reset` then shows instructions, OR implements inline password change if backend supports it

**Step 2: Commit**

```bash
git add web/app/\(dashboard\)/settings/
git commit -m "feat: add settings page with password change"
```

---

### Task 13: Root redirect and 404

**Files:**
- Modify: `web/app/page.tsx`
- Create: `web/app/not-found.tsx`

**Step 1: Root page redirects to /features or /login**

Modify `web/app/page.tsx`:
```typescript
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem("aba_token");
    router.replace(token ? "/features" : "/login");
  }, [router]);

  return null;
}
```

**Step 2: Create not-found page**

Create `web/app/not-found.tsx`:
```typescript
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center">
      <h1 className="text-6xl font-bold text-gray-300 mb-4">404</h1>
      <p className="text-gray-500 mb-6">页面不存在</p>
      <Button asChild>
        <Link href="/features">返回首页</Link>
      </Button>
    </div>
  );
}
```

**Step 3: Commit**

```bash
git add web/app/page.tsx web/app/not-found.tsx
git commit -m "feat: add root redirect and 404 page"
```

---

### Task 14: End-to-end smoke test

**Step 1: Start both servers**

Terminal 1:
```bash
cd D:/OneDrive/wxob/ABA-Agent-Starter/api && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Terminal 2:
```bash
cd D:/OneDrive/wxob/ABA-Agent-Starter/web && npm run dev
```

**Step 2: Manual smoke test checklist**

- [ ] Visit http://localhost:3000 → redirects to /login
- [ ] Click "注册组织" → register form renders
- [ ] Register a new org → auto-login → /features
- [ ] Features page shows skill cards with category filter
- [ ] Click a feature card → form modal opens with correct fields
- [ ] Submit a job → redirects to /jobs
- [ ] Jobs page shows the submitted job
- [ ] Navigate to /clients → client list renders
- [ ] Navigate to /users (admin) → user table renders
- [ ] Invite a user → token displayed
- [ ] Logout → back to /login
- [ ] Forgot password page renders

**Step 3: Fix any issues found**

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete frontend redesign with Next.js + shadcn/ui"
```
