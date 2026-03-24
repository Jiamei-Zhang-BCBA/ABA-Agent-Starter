"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "./auth";
import { api } from "./api";
import type { User } from "@/types";

export function useRequireAuth() {
  const router = useRouter();
  const { token, user, setUser, hydrate } = useAuth();

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    if (!token) {
      router.push("/login");
      return;
    }
    if (!user) {
      api.get<User>("/auth/me").then(setUser).catch(() => {
        router.push("/login");
      });
    }
  }, [token, user, router, setUser]);

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
