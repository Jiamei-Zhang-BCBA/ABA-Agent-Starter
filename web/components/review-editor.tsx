"use client";

import { useState } from "react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { MarkdownViewer } from "./markdown-viewer";
import { Loader2, Send, Undo2 } from "lucide-react";
import type { Review } from "@/types";

interface ReviewEditorProps {
  review: Review;
  onApprove: () => void;
  onReject: () => void;
  onCancel: () => void;
}

interface AIReviseResponse {
  revised_content: string;
  input_tokens: number;
  output_tokens: number;
}

export function ReviewEditor({
  review,
  onApprove,
  onReject,
  onCancel,
}: ReviewEditorProps) {
  const [content, setContent] = useState(review.output_content);
  const [instruction, setInstruction] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [approveLoading, setApproveLoading] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectComments, setRejectComments] = useState("");
  const [rejectLoading, setRejectLoading] = useState(false);
  const [history, setHistory] = useState<string[]>([]);

  async function handleAIRevise() {
    const trimmed = instruction.trim();
    if (!trimmed) {
      toast.error("请输入修改指令");
      return;
    }
    setAiLoading(true);
    try {
      const res = await api.post<AIReviseResponse>("/reviews/ai-revise", {
        content,
        instruction: trimmed,
      });
      setHistory((prev) => [...prev, content]);
      setContent(res.revised_content);
      setInstruction("");
      toast.success("AI 修改完成");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "AI 修改失败");
    } finally {
      setAiLoading(false);
    }
  }

  function handleUndo() {
    if (history.length === 0) return;
    const previous = history[history.length - 1];
    setHistory((h) => h.slice(0, -1));
    setContent(previous);
    toast.info("已撤销");
  }

  async function handleApprove() {
    setApproveLoading(true);
    try {
      const modified =
        content !== review.output_content ? content : undefined;
      await api.post(`/reviews/${review.id}/approve`, {
        modified_content: modified,
      });
      toast.success("已批准");
      onApprove();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "操作失败");
    } finally {
      setApproveLoading(false);
    }
  }

  async function handleReject() {
    if (!rejectComments.trim()) {
      toast.error("请填写拒绝原因");
      return;
    }
    setRejectLoading(true);
    try {
      await api.post(`/reviews/${review.id}/reject`, {
        comments: rejectComments,
      });
      toast.success("已拒绝");
      onReject();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "操作失败");
    } finally {
      setRejectLoading(false);
    }
  }

  function handleCancel() {
    if (content !== review.output_content) {
      const confirmed = window.confirm("你有未保存的修改，确定要离开吗？");
      if (!confirmed) return;
    }
    onCancel();
  }

  const hasChanges = content !== review.output_content;
  const canUndo = history.length > 0;

  return (
    <div className="flex flex-col h-[calc(100vh-120px)]">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-1 py-2">
        <span className="text-sm text-muted-foreground">
          任务 {review.job_id.slice(0, 8)}...
          {hasChanges && (
            <span className="ml-2 text-orange-500">（已修改）</span>
          )}
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleUndo}
          disabled={!canUndo}
        >
          <Undo2 className="w-4 h-4 mr-1" />
          撤销
        </Button>
      </div>

      {/* Editor with edit/preview tabs */}
      <Tabs defaultValue="edit" className="flex-1 flex flex-col min-h-0">
        <TabsList>
          <TabsTrigger value="edit">编辑</TabsTrigger>
          <TabsTrigger value="preview">预览</TabsTrigger>
        </TabsList>
        <TabsContent value="edit" className="flex-1 min-h-0">
          <Textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            className="font-mono text-sm h-full min-h-[300px] resize-none"
          />
        </TabsContent>
        <TabsContent value="preview" className="flex-1 overflow-y-auto min-h-0">
          <div className="border rounded-md p-4 min-h-[300px]">
            <MarkdownViewer content={content} />
          </div>
        </TabsContent>
      </Tabs>

      {/* AI Assist Bar */}
      <div className="flex gap-2 items-center border rounded-md p-2 bg-muted/30 mt-3">
        <Input
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          placeholder="输入 AI 修改指令... (例: 把语气改得更温柔)"
          className="flex-1"
          disabled={aiLoading}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleAIRevise();
            }
          }}
        />
        <Button
          size="sm"
          onClick={handleAIRevise}
          disabled={aiLoading || !instruction.trim()}
        >
          {aiLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Send className="w-4 h-4" />
          )}
        </Button>
      </div>

      {/* Footer Actions */}
      <div className="flex items-center justify-between border-t pt-3 mt-3">
        <Button
          variant="destructive"
          size="sm"
          onClick={() => setRejectOpen(true)}
        >
          拒绝
        </Button>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleCancel}>
            取消
          </Button>
          <Button onClick={handleApprove} disabled={approveLoading}>
            {approveLoading ? "提交中..." : "批准"}
          </Button>
        </div>
      </div>

      {/* Reject Dialog */}
      <Dialog open={rejectOpen} onOpenChange={setRejectOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>拒绝审核</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>拒绝原因 *</Label>
              <Textarea
                value={rejectComments}
                onChange={(e) => setRejectComments(e.target.value)}
                placeholder="请说明拒绝原因"
                rows={4}
                required
              />
            </div>
            <div className="flex justify-end space-x-2">
              <Button variant="outline" onClick={() => setRejectOpen(false)}>
                取消
              </Button>
              <Button
                variant="destructive"
                onClick={handleReject}
                disabled={rejectLoading}
              >
                {rejectLoading ? "提交中..." : "确认拒绝"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
