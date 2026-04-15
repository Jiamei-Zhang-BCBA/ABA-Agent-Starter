"use client";

import { useState } from "react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { Label } from "@/components/ui/label";
import { MarkdownViewer } from "./markdown-viewer";
import { ReviewEditor } from "./review-editor";
import type { Review } from "@/types";

interface ReviewCardProps {
  review: Review;
  onAction: () => void;
}

export function ReviewCard({ review, onAction }: ReviewCardProps) {
  const [editorOpen, setEditorOpen] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [comments, setComments] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleReject() {
    if (!comments.trim()) {
      toast.error("请填写拒绝原因");
      return;
    }
    setLoading(true);
    try {
      await api.post(`/reviews/${review.id}/reject`, { comments });
      toast.success("已拒绝");
      setRejectOpen(false);
      onAction();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "操作失败");
    } finally {
      setLoading(false);
    }
  }

  const statusLabel = review.status === "pending" ? "待审核" : review.status === "approved" ? "已批准" : "已拒绝";
  const statusVariant = review.status === "pending" ? "outline" : review.status === "approved" ? "default" : "destructive";

  return (
    <>
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">任务 {review.job_id.slice(0, 8)}...</CardTitle>
            <Badge variant={statusVariant as "default" | "secondary" | "destructive" | "outline"}>
              {statusLabel}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="border rounded-md p-3 max-h-48 overflow-y-auto text-sm">
            <MarkdownViewer content={review.output_content.slice(0, 500) + (review.output_content.length > 500 ? "\n\n..." : "")} />
          </div>
          {review.status === "pending" && (
            <div className="flex space-x-2">
              <Button size="sm" onClick={() => setEditorOpen(true)}>
                审核
              </Button>
              <Button size="sm" variant="destructive" onClick={() => setRejectOpen(true)}>
                拒绝
              </Button>
            </div>
          )}
          {review.comments && (
            <p className="text-sm text-muted-foreground">
              备注：{review.comments}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Full-screen Review Editor */}
      <Sheet open={editorOpen} onOpenChange={setEditorOpen}>
        <SheetContent className="w-full sm:max-w-none sm:w-[80vw] lg:w-[70vw] overflow-y-auto">
          <SheetHeader>
            <SheetTitle>审核编辑</SheetTitle>
            <SheetDescription>
              直接编辑文档或使用底部 AI 辅助修改，满意后点击"批准"
            </SheetDescription>
          </SheetHeader>
          {editorOpen && (
            <ReviewEditor
              review={review}
              onApprove={() => {
                setEditorOpen(false);
                onAction();
              }}
              onReject={() => {
                setEditorOpen(false);
                onAction();
              }}
              onCancel={() => setEditorOpen(false)}
            />
          )}
        </SheetContent>
      </Sheet>

      {/* Quick Reject Dialog */}
      <Dialog open={rejectOpen} onOpenChange={setRejectOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>拒绝审核</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>拒绝原因 *</Label>
              <Textarea
                value={comments}
                onChange={(e) => setComments(e.target.value)}
                placeholder="请说明拒绝原因"
                rows={4}
                required
              />
            </div>
            <div className="flex justify-end space-x-2">
              <Button variant="outline" onClick={() => setRejectOpen(false)}>
                取消
              </Button>
              <Button variant="destructive" onClick={handleReject} disabled={loading}>
                {loading ? "提交中..." : "确认拒绝"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
