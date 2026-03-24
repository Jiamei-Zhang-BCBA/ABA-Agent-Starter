"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useRequireRole } from "@/lib/hooks";
import { ReviewCard } from "@/components/review-card";
import type { Review } from "@/types";

export default function ReviewsPage() {
  const { user } = useRequireRole("org_admin", "bcba");
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchReviews = useCallback(() => {
    setLoading(true);
    api
      .get<{ reviews: Review[] }>("/reviews")
      .then((res) => setReviews(res.reviews))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (user) fetchReviews();
  }, [user, fetchReviews]);

  if (!user) return null;

  if (loading) {
    return <div className="text-center py-12 text-gray-400">加载中...</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">审核队列</h1>
        <p className="text-muted-foreground mt-1">审核和管理输出内容</p>
      </div>

      {reviews.length === 0 ? (
        <div className="text-center py-12 text-gray-400">暂无待审核内容</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {reviews.map((review) => (
            <ReviewCard
              key={review.id}
              review={review}
              onAction={fetchReviews}
            />
          ))}
        </div>
      )}
    </div>
  );
}
