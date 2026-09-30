"use client";

import { useMutation } from "@tanstack/react-query";

const initiateGoogleLogin = (nextPath?: string) => {
  const baseUrl = process.env.NEXT_PUBLIC_BACKEND_URL?.replace("/api/v1", "") || "https://siyaf.onrender.com";
  const next = nextPath || "/onboarding";
  window.location.href = `${baseUrl}/api/v1/auth/google?next=${encodeURIComponent(next)}`
};

export const useGoogleLogin = () => {
  return useMutation({
    mutationFn: async (nextPath?: string) => {
      initiateGoogleLogin(nextPath);
    },
    onError: (error) => {
      console.error("Failed to initiate Google Login:", error);
    },
  });
};