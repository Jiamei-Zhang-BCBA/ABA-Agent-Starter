"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { MarkdownViewer } from "@/components/markdown-viewer";

interface VaultFileViewerProps {
  path: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function VaultFileViewer({ path, open, onOpenChange }: VaultFileViewerProps) {
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadFile(filePath: string) {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<{ path: string; content: string }>(
        `/vault/read?path=${encodeURIComponent(filePath)}`,
      );
      setContent(res.content);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
      setContent(null);
    } finally {
      setLoading(false);
    }
  }

  function handleOpenChange(isOpen: boolean) {
    if (isOpen && path) {
      loadFile(path);
    }
    if (!isOpen) {
      setContent(null);
      setError(null);
    }
    onOpenChange(isOpen);
  }

  function downloadFile() {
    if (!path) return;
    const filename = path.split("/").pop() || "file.md";
    const blob = new Blob([content || ""], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <Sheet open={open} onOpenChange={handleOpenChange}>
      <SheetContent className="w-full sm:max-w-2xl overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="text-sm font-mono truncate">
            {path || "文件预览"}
          </SheetTitle>
        </SheetHeader>
        <div className="mt-4">
          {loading && (
            <div className="text-center py-8 text-gray-400">加载中...</div>
          )}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-md p-4 text-red-700 text-sm">
              {error}
            </div>
          )}
          {content !== null && !loading && (
            <div className="space-y-3">
              <div className="flex justify-end">
                <Button variant="outline" size="sm" onClick={downloadFile}>
                  下载
                </Button>
              </div>
              <div className="border rounded-md p-4">
                <MarkdownViewer content={content} />
              </div>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
