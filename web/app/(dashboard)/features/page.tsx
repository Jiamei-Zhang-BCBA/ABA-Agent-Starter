"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { FeatureCard } from "@/components/feature-card";
import { JobFormModal } from "@/components/job-form-modal";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { Feature, FeatureListResponse } from "@/types";

export default function FeaturesPage() {
  const searchParams = useSearchParams();
  const preselectedFeatureId = searchParams.get("feature");
  const preselectedClientId = searchParams.get("client_id");

  const [features, setFeatures] = useState<Feature[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedFeature, setSelectedFeature] = useState<Feature | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [activeCategory, setActiveCategory] = useState("all");

  useEffect(() => {
    api
      .get<FeatureListResponse>("/features")
      .then((res) => {
        setFeatures(res.features);
        // Auto-open modal if feature is preselected from client page
        if (preselectedFeatureId) {
          const f = res.features.find((feat) => feat.id === preselectedFeatureId);
          if (f) {
            setSelectedFeature(f);
            setModalOpen(true);
          }
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [preselectedFeatureId]);

  const categories = [
    "all",
    ...Array.from(new Set(features.map((f) => f.category))),
  ];

  const filteredFeatures =
    activeCategory === "all"
      ? features
      : features.filter((f) => f.category === activeCategory);

  function handleCardClick(feature: Feature) {
    setSelectedFeature(feature);
    setModalOpen(true);
  }

  if (loading) {
    return (
      <div className="text-center py-12 text-gray-400">加载功能列表中...</div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">功能中心</h1>
        <p className="text-muted-foreground mt-1">选择一个功能来创建新任务</p>
      </div>

      {categories.length > 2 && (
        <Tabs value={activeCategory} onValueChange={setActiveCategory}>
          <TabsList>
            {categories.map((cat) => (
              <TabsTrigger key={cat} value={cat}>
                {cat === "all" ? "全部" : cat}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      )}

      {filteredFeatures.length === 0 ? (
        <div className="text-center py-12 text-gray-400">暂无可用功能</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredFeatures.map((feature) => (
            <FeatureCard
              key={feature.id}
              feature={feature}
              onClick={() => handleCardClick(feature)}
            />
          ))}
        </div>
      )}

      <JobFormModal
        feature={selectedFeature}
        open={modalOpen}
        onClose={() => {
          setModalOpen(false);
          setSelectedFeature(null);
        }}
        defaultClientId={preselectedClientId || undefined}
      />
    </div>
  );
}
