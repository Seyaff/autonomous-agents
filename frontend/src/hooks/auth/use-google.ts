"use client";

import { useMutation } from "@tanstack/react-query";
import API from "@/lib/axios-client";

const initiateGoogleLogin = () => {
  window.location.href = `http://localhost:8000/api/v1/auth/google`
};

export const useGoogleLogin = () => {
  return useMutation({
    mutationFn: async () => initiateGoogleLogin(),
    onError: (error) => {
      console.error("Failed to initiate Google Login:", error);
    },
  });
};