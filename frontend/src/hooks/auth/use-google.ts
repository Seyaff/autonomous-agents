"use client";

import { useMutation } from "@tanstack/react-query";

const initiateGoogleLogin = (nextPath?: string) => {
  const next = nextPath || "/setup";
  // Use relative path - will be proxied by Next.js rewrites
  window.location.href = `/api/auth/google?next=${encodeURIComponent(next)}`
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