"use client";

import { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { ClientAssignment, Staff } from "@/types";

const RELATION_LABELS: Record<string, string> = {
  teacher: "老师",
  parent: "家长",
};

const ROLE_LABELS: Record<string, string> = {
  org_admin: "管理员",
  bcba: "BCBA",
  teacher: "老师",
  parent: "家长",
};

interface StaffAssignmentPanelProps {
  clientId: string;
}

export function StaffAssignmentPanel({ clientId }: StaffAssignmentPanelProps) {
  const { user } = useAuth();
  const [assignments, setAssignments] = useState<ClientAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [staff, setStaff] = useState<Staff[]>([]);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [selectedRelation, setSelectedRelation] = useState("teacher");
  const [submitting, setSubmitting] = useState(false);

  const isSupervisor = user?.role === "org_admin" || user?.role === "bcba";

  const fetchAssignments = useCallback(() => {
    setLoading(true);
    api
      .get<{ assignments: ClientAssignment[] }>(`/clients/${clientId}/assignments`)
      .then((res) => setAssignments(res.assignments))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [clientId]);

  useEffect(() => {
    fetchAssignments();
  }, [fetchAssignments]);

  const loadStaffForRelation = useCallback(
    (relation: string) => {
      // When assigning a parent, the staff list must include parent users too.
      const qs = relation === "parent" ? "?include_parents=true" : "";
      api
        .get<{ staff: Staff[] }>(`/staff${qs}`)
        .then((res) => {
          const assignedIds = new Set(assignments.map((a) => a.user_id));
          // Only show users whose role matches the chosen relation
          // (teacher relation → teacher/bcba; parent relation → parent).
          const roleFilter =
            relation === "parent"
              ? (r: string) => r === "parent"
              : (r: string) => r === "teacher" || r === "bcba";
          setStaff(
            res.staff.filter((s) => !assignedIds.has(s.id) && roleFilter(s.role)),
          );
        })
        .catch(() => {});
    },
    [assignments],
  );

  function openAssignDialog() {
    setSelectedUserId("");
    setSelectedRelation("teacher");
    loadStaffForRelation("teacher");
    setDialogOpen(true);
  }

  function handleRelationChange(v: string | null) {
    if (!v) return;
    setSelectedRelation(v);
    setSelectedUserId(""); // reset selection since the list will change
    loadStaffForRelation(v);
  }

  async function handleAssign() {
    if (!selectedUserId) return;
    setSubmitting(true);
    try {
      await api.post(`/clients/${clientId}/assignments`, {
        user_id: selectedUserId,
        relation: selectedRelation,
      });
      toast.success("分配成功");
      setDialogOpen(false);
      fetchAssignments();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "分配失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleUnassign(linkId: string) {
    try {
      await api.delete(`/clients/${clientId}/assignments/${linkId}`);
      toast.success("已取消分配");
      fetchAssignments();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "操作失败");
    }
  }

  if (loading) {
    return <div className="text-sm text-gray-400">加载团队信息...</div>;
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">分配团队</h3>
        {isSupervisor && (
          <Button size="sm" onClick={openAssignDialog}>
            分配人员
          </Button>
        )}
      </div>

      {assignments.length === 0 ? (
        <p className="text-sm text-gray-400">暂未分配人员</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>姓名</TableHead>
              <TableHead>角色</TableHead>
              <TableHead>关系</TableHead>
              {isSupervisor && <TableHead>操作</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {assignments.map((a) => (
              <TableRow key={a.id}>
                <TableCell className="font-medium">{a.user_name}</TableCell>
                <TableCell>
                  <Badge variant="secondary">
                    {ROLE_LABELS[a.user_role] || a.user_role}
                  </Badge>
                </TableCell>
                <TableCell>{RELATION_LABELS[a.relation] || a.relation}</TableCell>
                {isSupervisor && (
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-red-500 hover:text-red-700"
                      onClick={() => handleUnassign(a.id)}
                    >
                      移除
                    </Button>
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>分配人员到个案</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>选择人员</Label>
              <Select value={selectedUserId} onValueChange={(v) => v && setSelectedUserId(v)}>
                <SelectTrigger>
                  <SelectValue placeholder="请选择" />
                </SelectTrigger>
                <SelectContent>
                  {staff.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.name} ({ROLE_LABELS[s.role] || s.role})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>关系</Label>
              <Select value={selectedRelation} onValueChange={handleRelationChange}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="teacher">老师</SelectItem>
                  <SelectItem value="parent">家长</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex justify-end space-x-2">
              <Button variant="outline" onClick={() => setDialogOpen(false)}>
                取消
              </Button>
              <Button onClick={handleAssign} disabled={!selectedUserId || submitting}>
                {submitting ? "分配中..." : "确认分配"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
