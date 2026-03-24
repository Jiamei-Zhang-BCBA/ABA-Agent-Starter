"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Feature } from "@/types";

interface FeatureCardProps {
  feature: Feature;
  onClick: () => void;
}

export function FeatureCard({ feature, onClick }: FeatureCardProps) {
  return (
    <Card
      className="cursor-pointer hover:shadow-md transition-shadow"
      onClick={onClick}
    >
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <span className="text-2xl">{feature.icon || "🔧"}</span>
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
