"use client";

import { useState, useCallback } from "react";
import {
  ChevronRight,
  ChevronDown,
  Folder,
  FolderOpen,
  FileText,
  Loader2,
  Database,
  Users,
  ClipboardList,
  UserCheck,
  BookOpen,
  MessageSquare,
} from "lucide-react";
import { vaultApi } from "@/lib/vault-api";
import type { VaultRoot, VaultItem } from "@/types";

// Map icon names from API to lucide components
const ICON_MAP: Record<string, React.ElementType> = {
  database: Database,
  users: Users,
  clipboard: ClipboardList,
  "user-check": UserCheck,
  "book-open": BookOpen,
  "message-square": MessageSquare,
  "file-text": FileText,
};

interface TreeNode {
  path: string;
  name: string;
  label?: string;
  type: "file" | "directory";
  icon?: string;
  children: TreeNode[];
  isExpanded: boolean;
  isLoaded: boolean;
}

interface VaultTreeProps {
  roots: VaultRoot[];
  selectedPath: string | null;
  onSelectFile: (path: string) => void;
  expandPath?: string | null;
}

function rootToNode(root: VaultRoot): TreeNode {
  return {
    path: root.path,
    name: root.path,
    label: root.label,
    type: "directory",
    icon: root.icon,
    children: [],
    isExpanded: false,
    isLoaded: false,
  };
}

function itemToNode(item: VaultItem): TreeNode {
  return {
    path: item.path,
    name: item.name,
    type: item.type,
    children: [],
    isExpanded: false,
    isLoaded: false,
  };
}

function updateTree(
  nodes: TreeNode[],
  targetPath: string,
  updater: (node: TreeNode) => TreeNode,
): TreeNode[] {
  return nodes.map((node) => {
    if (node.path === targetPath) {
      return updater(node);
    }
    if (targetPath.startsWith(node.path + "/")) {
      return { ...node, children: updateTree(node.children, targetPath, updater) };
    }
    return node;
  });
}

export function VaultTree({ roots, selectedPath, onSelectFile, expandPath }: VaultTreeProps) {
  const [tree, setTree] = useState<TreeNode[]>(() => roots.map(rootToNode));
  const [loadingPaths, setLoadingPaths] = useState<Set<string>>(new Set());

  // Sync roots when they change
  if (roots.length > 0 && tree.length === 0) {
    setTree(roots.map(rootToNode));
  }

  const loadChildren = useCallback(async (path: string) => {
    setLoadingPaths((prev) => new Set(prev).add(path));
    try {
      const data = await vaultApi.listDirectory(path);
      const children = data.items.map(itemToNode);
      setTree((prev) =>
        updateTree(prev, path, (node) => ({
          ...node,
          children,
          isExpanded: true,
          isLoaded: true,
        })),
      );
    } finally {
      setLoadingPaths((prev) => {
        const next = new Set(prev);
        next.delete(path);
        return next;
      });
    }
  }, []);

  const toggleDirectory = useCallback(
    (node: TreeNode) => {
      if (node.type !== "directory") return;

      if (!node.isLoaded) {
        loadChildren(node.path);
      } else {
        setTree((prev) =>
          updateTree(prev, node.path, (n) => ({
            ...n,
            isExpanded: !n.isExpanded,
          })),
        );
      }
    },
    [loadChildren],
  );

  const handleClick = useCallback(
    (node: TreeNode) => {
      if (node.type === "directory") {
        toggleDirectory(node);
      } else {
        onSelectFile(node.path);
      }
    },
    [toggleDirectory, onSelectFile],
  );

  return (
    <div className="text-sm">
      {tree.map((node) => (
        <TreeNodeItem
          key={node.path}
          node={node}
          depth={0}
          selectedPath={selectedPath}
          loadingPaths={loadingPaths}
          onClick={handleClick}
        />
      ))}
    </div>
  );
}

interface TreeNodeItemProps {
  node: TreeNode;
  depth: number;
  selectedPath: string | null;
  loadingPaths: Set<string>;
  onClick: (node: TreeNode) => void;
}

function TreeNodeItem({ node, depth, selectedPath, loadingPaths, onClick }: TreeNodeItemProps) {
  const isLoading = loadingPaths.has(node.path);
  const isSelected = node.path === selectedPath;
  const isDir = node.type === "directory";

  const RootIcon = node.icon ? ICON_MAP[node.icon] : null;

  return (
    <div>
      <button
        onClick={() => onClick(node)}
        className={`w-full flex items-center gap-1.5 py-1 px-2 rounded-md text-left hover:bg-gray-100 transition-colors ${
          isSelected ? "bg-indigo-50 text-indigo-700" : "text-gray-700"
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        {/* Expand/collapse chevron for directories */}
        {isDir ? (
          isLoading ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin text-gray-400 shrink-0" />
          ) : node.isExpanded ? (
            <ChevronDown className="w-3.5 h-3.5 text-gray-400 shrink-0" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 text-gray-400 shrink-0" />
          )
        ) : (
          <span className="w-3.5 shrink-0" />
        )}

        {/* Icon */}
        {RootIcon ? (
          <RootIcon className="w-4 h-4 text-gray-500 shrink-0" />
        ) : isDir ? (
          node.isExpanded ? (
            <FolderOpen className="w-4 h-4 text-amber-500 shrink-0" />
          ) : (
            <Folder className="w-4 h-4 text-amber-500 shrink-0" />
          )
        ) : (
          <FileText className="w-4 h-4 text-gray-400 shrink-0" />
        )}

        {/* Label */}
        <span className="truncate">{node.label || node.name}</span>
      </button>

      {/* Children */}
      {isDir && node.isExpanded && node.children.length > 0 && (
        <div>
          {node.children.map((child) => (
            <TreeNodeItem
              key={child.path}
              node={child}
              depth={depth + 1}
              selectedPath={selectedPath}
              loadingPaths={loadingPaths}
              onClick={onClick}
            />
          ))}
        </div>
      )}

      {/* Empty directory message */}
      {isDir && node.isExpanded && node.isLoaded && node.children.length === 0 && (
        <div
          className="text-xs text-gray-400 py-1"
          style={{ paddingLeft: `${(depth + 1) * 16 + 8}px` }}
        >
          (空)
        </div>
      )}
    </div>
  );
}
