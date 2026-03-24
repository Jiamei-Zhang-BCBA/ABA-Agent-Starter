"use client";

import { useState } from "react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { MarkdownViewer } from "./markdown-viewer";

interface MarkdownEditorProps {
  jobId: string;
  initialContent: string;
  onSave: (content: string) => void;
  onCancel: () => void;
}

export function MarkdownEditor({ jobId, initialContent, onSave, onCancel }: MarkdownEditorProps) {
  const [content, setContent] = useState(initialContent);
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      await api.patch(`/jobs/${jobId}/output`, { output_content: content });
      toast.success("保存成功");
      onSave(content);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-3">
      <Tabs defaultValue="edit">
        <TabsList>
          <TabsTrigger value="edit">编辑</TabsTrigger>
          <TabsTrigger value="preview">预览</TabsTrigger>
        </TabsList>
        <TabsContent value="edit">
          <Textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={16}
            className="font-mono text-sm"
          />
        </TabsContent>
        <TabsContent value="preview">
          <div className="border rounded-md p-4 min-h-[300px]">
            <MarkdownViewer content={content} />
          </div>
        </TabsContent>
      </Tabs>
      <div className="flex justify-end space-x-2">
        <Button variant="outline" onClick={onCancel}>
          取消
        </Button>
        <Button onClick={handleSave} disabled={saving}>
          {saving ? "保存中..." : "保存"}
        </Button>
      </div>
    </div>
  );
}
