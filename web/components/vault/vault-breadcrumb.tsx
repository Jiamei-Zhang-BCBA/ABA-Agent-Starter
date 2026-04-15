"use client";

import { Fragment } from "react";
import { ChevronRight, Home } from "lucide-react";

interface VaultBreadcrumbProps {
  path: string;
  onNavigate: (path: string) => void;
}

export function VaultBreadcrumb({ path, onNavigate }: VaultBreadcrumbProps) {
  const segments = path ? path.split("/").filter(Boolean) : [];

  return (
    <nav className="flex items-center space-x-1 text-sm text-gray-500">
      <button
        onClick={() => onNavigate("")}
        className="flex items-center gap-1 hover:text-gray-900 transition-colors px-1.5 py-0.5 rounded hover:bg-gray-100"
      >
        <Home className="w-3.5 h-3.5" />
        <span>根目录</span>
      </button>
      {segments.map((segment, i) => {
        const segmentPath = segments.slice(0, i + 1).join("/");
        const isLast = i === segments.length - 1;
        return (
          <Fragment key={segmentPath}>
            <ChevronRight className="w-3.5 h-3.5 text-gray-300 shrink-0" />
            <button
              onClick={() => onNavigate(segmentPath)}
              className={`px-1.5 py-0.5 rounded transition-colors truncate max-w-[200px] ${
                isLast
                  ? "text-gray-900 font-medium"
                  : "hover:text-gray-900 hover:bg-gray-100"
              }`}
            >
              {segment}
            </button>
          </Fragment>
        );
      })}
    </nav>
  );
}
