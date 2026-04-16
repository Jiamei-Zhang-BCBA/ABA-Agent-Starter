"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { FeatureIcon } from "@/components/feature-icon";
import type { Feature } from "@/types";

interface FeatureCardProps {
  feature: Feature;
  onClick: () => void;
}

export function FeatureCard({ feature, onClick }: FeatureCardProps) {
  const isDestructive = feature.is_destructive === true;
  return (
    <Card
      className={
        "cursor-pointer hover:shadow-md transition-shadow " +
        (isDestructive ? "border-red-300 hover:border-red-400" : "")
      }
      onClick={onClick}
    >
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <FeatureIcon name={feature.icon || "wrench"} />
          <div className="flex items-center gap-1">
            {isDestructive && (
              <Badge variant="destructive" className="text-[10px]">
                ⚠️ 不可逆
              </Badge>
            )}
            <Badge variant="secondary">{feature.category}</Badge>
          </div>
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
