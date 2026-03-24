"use client";

import { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import { useRequireRole } from "@/lib/hooks";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { UserDetail, UserListResponse, InvitationResponse } from "@/types";

const ROLE_LABELS: Record<string, string> = {
  org_admin: "管理员",
  bcba: "BCBA",
  teacher: "老师",
  parent: "家长",
};

function formatTime(iso: string | null) {
  if (!iso) return "从未";
  return new Date(iso).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function UsersPage() {
  const { user: currentUser } = useRequireRole("org_admin");
  const [users, setUsers] = useState<UserDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("teacher");
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteResult, setInviteResult] = useState<InvitationResponse | null>(null);
  const [confirmDeactivate, setConfirmDeactivate] = useState<string | null>(null);

  const fetchUsers = useCallback(() => {
    setLoading(true);
    api
      .get<UserListResponse>("/users")
      .then((res) => setUsers(res.users))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (currentUser) fetchUsers();
  }, [currentUser, fetchUsers]);

  async function handleInvite() {
    if (!inviteEmail.trim()) return;
    setInviteLoading(true);
    try {
      const res = await api.post<InvitationResponse>("/users/invite", {
        email: inviteEmail,
        role: inviteRole,
      });
      setInviteResult(res);
      toast.success("邀请已发送");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "邀请失败");
    } finally {
      setInviteLoading(false);
    }
  }

  async function handleRoleChange(userId: string, newRole: string) {
    try {
      await api.patch(`/users/${userId}`, { role: newRole });
      toast.success("角色已更新");
      fetchUsers();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "更新失败");
    }
  }

  async function handleDeactivate(userId: string) {
    try {
      await api.delete(`/users/${userId}`);
      toast.success("用户已停用");
      setConfirmDeactivate(null);
      fetchUsers();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "操作失败");
    }
  }

  if (!currentUser) return null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">用户管理</h1>
          <p className="text-muted-foreground mt-1">管理组织成员</p>
        </div>
        <Button onClick={() => {
          setInviteOpen(true);
          setInviteEmail("");
          setInviteRole("teacher");
          setInviteResult(null);
        }}>
          邀请用户
        </Button>
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-400">加载中...</div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>姓名</TableHead>
              <TableHead>邮箱</TableHead>
              <TableHead>角色</TableHead>
              <TableHead>状态</TableHead>
              <TableHead>最近登录</TableHead>
              <TableHead>操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.map((u) => (
              <TableRow key={u.id}>
                <TableCell className="font-medium">{u.name}</TableCell>
                <TableCell>{u.email}</TableCell>
                <TableCell>
                  {u.id === currentUser.id ? (
                    <Badge>{ROLE_LABELS[u.role] || u.role}</Badge>
                  ) : (
                    <Select
                      value={u.role}
                      onValueChange={(v) => v && handleRoleChange(u.id, v)}
                    >
                      <SelectTrigger className="w-28">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="org_admin">管理员</SelectItem>
                        <SelectItem value="bcba">BCBA</SelectItem>
                        <SelectItem value="teacher">老师</SelectItem>
                        <SelectItem value="parent">家长</SelectItem>
                      </SelectContent>
                    </Select>
                  )}
                </TableCell>
                <TableCell>
                  <Badge variant={u.is_active ? "default" : "secondary"}>
                    {u.is_active ? "活跃" : "已停用"}
                  </Badge>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {formatTime(u.last_login_at)}
                </TableCell>
                <TableCell>
                  {u.id !== currentUser.id && u.is_active && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-red-500 hover:text-red-700"
                      onClick={() => setConfirmDeactivate(u.id)}
                    >
                      停用
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* Invite Dialog */}
      <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>邀请用户</DialogTitle>
          </DialogHeader>
          {inviteResult ? (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">邀请已创建，请将以下链接发送给被邀请者：</p>
              <div className="bg-gray-50 p-3 rounded-md text-sm font-mono break-all">
                {`${window.location.origin}/invite?token=${inviteResult.token}`}
              </div>
              <p className="text-xs text-muted-foreground">
                有效期至：{new Date(inviteResult.expires_at).toLocaleString("zh-CN")}
              </p>
              <Button className="w-full" onClick={() => setInviteOpen(false)}>
                关闭
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>邮箱</Label>
                <Input
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="请输入被邀请者邮箱"
                />
              </div>
              <div className="space-y-2">
                <Label>角色</Label>
                <Select value={inviteRole} onValueChange={(v) => v && setInviteRole(v)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="bcba">BCBA</SelectItem>
                    <SelectItem value="teacher">老师</SelectItem>
                    <SelectItem value="parent">家长</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex justify-end space-x-2">
                <Button variant="outline" onClick={() => setInviteOpen(false)}>
                  取消
                </Button>
                <Button onClick={handleInvite} disabled={inviteLoading}>
                  {inviteLoading ? "发送中..." : "发送邀请"}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Deactivate Confirm Dialog */}
      <Dialog open={!!confirmDeactivate} onOpenChange={() => setConfirmDeactivate(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认停用用户</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">停用后该用户将无法登录系统。此操作可以撤销。</p>
          <div className="flex justify-end space-x-2">
            <Button variant="outline" onClick={() => setConfirmDeactivate(null)}>
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={() => confirmDeactivate && handleDeactivate(confirmDeactivate)}
            >
              确认停用
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
