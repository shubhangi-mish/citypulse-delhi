"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { toast } from "@/components/toaster";
import { useProfile } from "@/hooks/use-profile";
import { api, ApiError } from "@/lib/api";

export function useRequireProfile() {
  const { profile } = useProfile();
  const router = useRouter();
  return (next?: string) => {
    if (profile) return true;
    toast.info("Create a quick profile to take part.");
    router.push(`/onboarding${next ? `?next=${encodeURIComponent(next)}` : ""}`);
    return false;
  };
}

export function useIssueActions(issueId: string) {
  const qc = useQueryClient();
  const refresh = () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: ["nearby"] }),
      qc.invalidateQueries({ queryKey: ["issue", issueId] }),
      qc.invalidateQueries({ queryKey: ["issues"] }),
      qc.invalidateQueries({ queryKey: ["activity"] }),
    ]);
  const onError = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Something went wrong.");

  const support = useMutation({
    mutationFn: (affected: boolean) => api.post<{ support_count: number }>(`/issues/${issueId}/support`, { affected }),
    onSuccess: (_, affected) => {
      toast.success(affected ? "Thanks — your neighbours can see this affects more people." : "Removed your confirmation.");
      refresh();
    },
    onError,
  });
  const follow = useMutation({
    mutationFn: (f: boolean) => api.post(`/issues/${issueId}/follow`, { follow: f }),
    onSuccess: (_, f) => {
      toast.success(f ? "Following — updates will appear in your notifications." : "Unfollowed.");
      refresh();
    },
    onError,
  });
  const comment = useMutation({
    mutationFn: (body: string) => api.post(`/issues/${issueId}/comments`, { body }),
    onSuccess: () => refresh(),
    onError,
  });
  return { support, follow, comment };
}
