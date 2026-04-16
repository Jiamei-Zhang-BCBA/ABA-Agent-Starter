"use client";

import { icons } from "lucide-react";

interface FeatureIconProps {
  /** kebab-case lucide icon name, e.g. "shield-check", "user-plus". */
  name: string;
  /** Tailwind size classes; default w-6 h-6. */
  className?: string;
  /** Optional override for the fallback emoji shown when icon is unknown. */
  fallback?: string;
}

function toPascalCase(kebab: string): string {
  return kebab
    .split("-")
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join("");
}

/**
 * Renders a lucide-react icon by its kebab-case name (matches what the
 * backend feature_registry stores in `icon`).
 *
 * If the name doesn't resolve, falls back to a 🔧 emoji so the layout
 * never breaks. Used by FeatureCard and the actions tab on client detail.
 */
export function FeatureIcon({ name, className = "w-6 h-6 text-indigo-500", fallback = "🔧" }: FeatureIconProps) {
  const pascal = toPascalCase(name || "wrench");
  const Icon = icons[pascal as keyof typeof icons];
  if (Icon) {
    return <Icon className={className} />;
  }
  return <span className="text-2xl leading-none">{fallback}</span>;
}
