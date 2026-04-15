"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { icons } from "lucide-react";
import type { Feature } from "@/types";

interface FeatureCardProps {
  feature: Feature;
  onClick: () => void;
}

function toPascalCase(kebab: string): string {
  return kebab
    .split("-")
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join("");
}

function FeatureIcon({ name }: { name: string }) {
  const pascal = toPascalCase(name);
  const Icon = icons[pascal as keyof typeof icons];
  if (Icon) {
    return <Icon className="w-6 h-6 text-indigo-500" />;
  }
  return <span className="text-2xl">🔧</span>;
}

export function FeatureCard({ feature, onClick }: FeatureCardProps) {
  return (
    <Card
      className="cursor-pointer hover:shadow-md transition-shadow"
      onClick={onClick}
    >
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <FeatureIcon name={feature.icon || "wrench"} />
          <Badge variant="secondary">{feature.category}</Badge>
        </div>
        <CardTitle className="text-lg">{feature.display_name}</CardTitle>
      </CardHeader>
      <CardContent>
        <CardDescription className="line-clamp-2">
          {feature.description}
        </CardDescription>
      </CardContent>
    </Card>
  );
}
