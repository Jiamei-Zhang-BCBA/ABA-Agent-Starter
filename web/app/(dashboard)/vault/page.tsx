"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { FolderOpen } from "lucide-react";
import { vaultApi } from "@/lib/vault-api";
import { VaultTree } from "@/components/vault/vault-tree";
import { VaultFilePreview } from "@/components/vault/vault-file-preview";
import { VaultBreadcrumb } from "@/components/vault/vault-breadcrumb";
import type { VaultRoot } from "@/types";

export default function VaultPage() {
  const searchParams = useSearchParams();
  const clientFilter = searchParams.get("client");

  const [roots, setRoots] = useState<VaultRoot[]>([]);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [currentDir, setCurrentDir] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    vaultApi
      .getRoots()
      .then((data) => setRoots(data.roots))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // Auto-navigate to client directory when ?client= param is present
  useEffect(() => {
    if (clientFilter && roots.length > 0) {
      setCurrentDir(`01-Clients/Client-${clientFilter}`);
    }
  }, [clientFilter, roots]);

  function handleBreadcrumbNavigate(path: string) {
    setCurrentDir(path);
    setSelectedPath(null);
  }

  if (loading) {
    return <div className="text-center py-12 text-gray-400">加载中...</div>;
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <FolderOpen className="w-6 h-6 text-amber-500" />
        <h1 className="text-2xl font-bold text-gray-900">文件库</h1>
      </div>

      {/* Breadcrumb */}
      {currentDir && (
        <VaultBreadcrumb path={currentDir} onNavigate={handleBreadcrumbNavigate} />
      )}

      {/* Main layout: tree + preview */}
      <div className="flex gap-4 h-[calc(100vh-200px)]">
        {/* Left: Tree Navigation */}
        <div className="w-64 shrink-0 border rounded-lg p-3 overflow-y-auto bg-gray-50">
          {roots.length === 0 ? (
            <div className="text-center py-4 text-gray-400 text-sm">暂无可访问的目录</div>
          ) : (
            <VaultTree
              roots={roots}
              selectedPath={selectedPath}
              onSelectFile={setSelectedPath}
              expandPath={currentDir}
            />
          )}
        </div>

        {/* Right: File Preview */}
        <div className="flex-1 border rounded-lg p-4 overflow-hidden">
          <VaultFilePreview selectedPath={selectedPath} />
        </div>
      </div>
    </div>
  );
}
