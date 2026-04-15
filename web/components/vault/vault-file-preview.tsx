"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { MarkdownViewer } from "@/components/markdown-viewer";
import { useAuth } from "@/lib/auth";
import { vaultApi } from "@/lib/vault-api";
import { FileText, Download, Sparkles, Loader2, Check, X, Undo2 } from "lucide-react";

interface VaultFilePreviewProps {
  selectedPath: string | null;
}

type ReviseStage = "idle" | "input" | "revising" | "preview" | "saving";

export function VaultFilePreview({ selectedPath }: VaultFilePreviewProps) {
  const { user } = useAuth();
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // AI revision state
  const [reviseStage, setReviseStage] = useState<ReviseStage>("idle");
  const [instruction, setInstruction] = useState("");
  const [revisedContent, setRevisedContent] = useState<string | null>(null);
  const [reviseError, setReviseError] = useState<string | null>(null);

  const isSupervisor = user?.role === "org_admin" || user?.role === "bcba";
  const isMarkdown = selectedPath?.endsWith(".md");

  useEffect(() => {
    if (!selectedPath) {
      setContent(null);
      setError(null);
      resetReviseState();
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    resetReviseState();

    vaultApi
      .readFile(selectedPath)
      .then((data) => {
        if (!cancelled) setContent(data.content);
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "加载失败");
          setContent(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedPath]);

  function resetReviseState() {
    setReviseStage("idle");
    setInstruction("");
    setRevisedContent(null);
    setReviseError(null);
  }

  function downloadFile() {
    if (!selectedPath || content === null) return;
    const filename = selectedPath.split("/").pop() || "file.md";
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function handleRevise() {
    if (!content || !instruction.trim()) return;
    setReviseStage("revising");
    setReviseError(null);

    try {
      const result = await vaultApi.aiRevise(content, instruction.trim(), selectedPath ?? undefined);
      setRevisedContent(result.revised_content);
      setReviseStage("preview");
    } catch (e) {
      setReviseError(e instanceof Error ? e.message : "AI 修改失败");
      setReviseStage("input");
    }
  }

  async function handleConfirmSave() {
    if (!selectedPath || revisedContent === null) return;
    setReviseStage("saving");
    setReviseError(null);

    try {
      await vaultApi.writeFile(selectedPath, revisedContent);
      setContent(revisedContent);
      resetReviseState();
    } catch (e) {
      setReviseError(e instanceof Error ? e.message : "保存失败");
      setReviseStage("preview");
    }
  }

  if (!selectedPath) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-400">
        <FileText className="w-12 h-12 mb-3" />
        <p>选择一个文件以预览</p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b pb-3 mb-4">
        <h3 className="text-sm font-mono text-gray-600 truncate flex-1 mr-4">
          {selectedPath}
        </h3>
        <div className="flex items-center gap-2 shrink-0">
          {isSupervisor && isMarkdown && content !== null && reviseStage === "idle" && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setReviseStage("input")}
            >
              <Sparkles className="w-4 h-4 mr-1" />
              AI 修改
            </Button>
          )}
          {content !== null && reviseStage === "idle" && (
            <Button variant="outline" size="sm" onClick={downloadFile}>
              <Download className="w-4 h-4 mr-1" />
              下载
            </Button>
          )}
        </div>
      </div>

      {/* AI Revision Panel */}
      {reviseStage !== "idle" && (
        <div className="border rounded-md p-4 mb-4 bg-indigo-50/50 space-y-3">
          {/* Input stage */}
          {(reviseStage === "input" || reviseStage === "revising") && (
            <>
              <label className="text-sm font-medium text-gray-700">
                修改指令
              </label>
              <textarea
                className="w-full border rounded-md p-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-300"
                rows={3}
                placeholder="描述你希望 AI 如何修改此文件..."
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                disabled={reviseStage === "revising"}
                maxLength={2000}
              />
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-400">
                  {instruction.length}/2000
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={resetReviseState}
                    disabled={reviseStage === "revising"}
                  >
                    取消
                  </Button>
                  <Button
                    size="sm"
                    onClick={handleRevise}
                    disabled={!instruction.trim() || reviseStage === "revising"}
                  >
                    {reviseStage === "revising" ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                        AI 处理中...
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-4 h-4 mr-1" />
                        生成修改
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </>
          )}

          {/* Preview stage */}
          {(reviseStage === "preview" || reviseStage === "saving") && (
            <>
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-indigo-700">
                  修改预览
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={resetReviseState}
                    disabled={reviseStage === "saving"}
                  >
                    <X className="w-4 h-4 mr-1" />
                    放弃
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setReviseStage("input")}
                    disabled={reviseStage === "saving"}
                  >
                    <Undo2 className="w-4 h-4 mr-1" />
                    重新修改
                  </Button>
                  <Button
                    size="sm"
                    onClick={handleConfirmSave}
                    disabled={reviseStage === "saving"}
                  >
                    {reviseStage === "saving" ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                        保存中...
                      </>
                    ) : (
                      <>
                        <Check className="w-4 h-4 mr-1" />
                        确认保存
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </>
          )}

          {/* Error */}
          {reviseError && (
            <div className="bg-red-50 border border-red-200 rounded-md p-3 text-red-700 text-sm">
              {reviseError}
            </div>
          )}
        </div>
      )}

      {/* Content */}
      {loading && (
        <div className="text-center py-8 text-gray-400">加载中...</div>
      )}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4 text-red-700 text-sm">
          {error}
        </div>
      )}
      {content !== null && !loading && (
        <div className="flex-1 overflow-y-auto">
          {reviseStage === "preview" || reviseStage === "saving" ? (
            /* Side-by-side diff view */
            <div className="grid grid-cols-2 gap-3 h-full">
              <div className="border rounded-md p-3 overflow-y-auto">
                <div className="text-xs font-medium text-gray-500 mb-2 pb-1 border-b">
                  修改前
                </div>
                <div className="text-sm">
                  <MarkdownViewer content={content} />
                </div>
              </div>
              <div className="border border-indigo-200 rounded-md p-3 overflow-y-auto bg-indigo-50/30">
                <div className="text-xs font-medium text-indigo-600 mb-2 pb-1 border-b border-indigo-200">
                  修改后
                </div>
                <div className="text-sm">
                  <MarkdownViewer content={revisedContent || ""} />
                </div>
              </div>
            </div>
          ) : (
            /* Normal view */
            <div className="border rounded-md p-4 h-full overflow-y-auto">
              <MarkdownViewer content={content} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
