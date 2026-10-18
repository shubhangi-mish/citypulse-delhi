"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Profile } from "@/lib/types";

export function useProfile() {
  const q = useQuery({
    queryKey: ["profile"],
    queryFn: () => api.get<{ profile: Profile | null }>("/profiles/me"),
    staleTime: 60_000,
  });
  return { profile: q.data?.profile ?? null, isLoading: q.isLoading, error: q.error, refetch: q.refetch };
}

export function useNotifications(enabled: boolean) {
  return useQuery({
    queryKey: ["notifications"],
    queryFn: () => api.get<{ items: { id: number; kind: string; entity_id: string; message: string; created_at: string; read: boolean }[]; unread: number }>("/profiles/me/notifications"),
    enabled,
    refetchInterval: 8_000,
  });
}

export function useOperator() {
  const q = useQuery({ queryKey: ["operator"], queryFn: () => api.get<{ username: string | null }>("/operator/me") });
  return { username: q.data?.username ?? null, isLoading: q.isLoading };
}

export function useInvalidate() {
  const qc = useQueryClient();
  return (...keys: string[][]) => Promise.all(keys.map((k) => qc.invalidateQueries({ queryKey: k })));
}

export { useMutation };
