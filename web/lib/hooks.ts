"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "./auth";
import { api } from "./api";
import type { User } from "@/types";

export function useRequireAuth() {
  const router = useRouter();
  const { token, user, setUser, hydrate, logout } = useAuth();
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    hydrate();
    setHydrated(true);
  }, [hydrate]);

  useEffect(() => {
    if (!hydrated) return;

    if (!token) {
      router.push("/login");
      return;
    }
    if (!user) {
      // api.get handles 401 → auto-refresh via refresh_token
      api.get<User>("/auth/me").then(setUser).catch(() => {
        logout();
        router.push("/login");
      });
    }
  }, [hydrated, token, user, router, setUser, logout]);

  return { user, token };
}

export function useRequireRole(...roles: string[]) {
  const { user } = useRequireAuth();

  useEffect(() => {
    if (user && !roles.includes(user.role)) {
      window.location.href = "/features";
    }
  }, [user, roles]);

  return { user };
}
