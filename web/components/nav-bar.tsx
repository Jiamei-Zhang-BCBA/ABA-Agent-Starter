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
  roles?: string[];
}

const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "概览" },
  { href: "/clients", label: "个案档案" },
  { href: "/vault", label: "文件库" },
  { href: "/jobs", label: "任务记录" },
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
