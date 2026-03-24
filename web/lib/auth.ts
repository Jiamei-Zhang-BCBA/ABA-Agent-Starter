import { create } from "zustand";
import type { User } from "@/types";

interface AuthState {
  token: string | null;
  refreshToken: string | null;
  user: User | null;
  setAuth: (token: string, refreshToken: string) => void;
  setUser: (user: User) => void;
  logout: () => void;
  hydrate: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  token: null,
  refreshToken: null,
  user: null,

  setAuth: (token, refreshToken) => {
    localStorage.setItem("aba_token", token);
    localStorage.setItem("aba_refresh_token", refreshToken);
    set({ token, refreshToken });
  },

  setUser: (user) => set({ user }),

  logout: () => {
    localStorage.removeItem("aba_token");
    localStorage.removeItem("aba_refresh_token");
    set({ token: null, refreshToken: null, user: null });
  },

  hydrate: () => {
    const token = localStorage.getItem("aba_token");
    const refreshToken = localStorage.getItem("aba_refresh_token");
    if (token) {
      set({ token, refreshToken });
    }
  },
}));
