"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { api } from "@/lib/api";
import { getToken } from "@/lib/auth";

export default function AppHomePage() {
  const router = useRouter();

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    void api.listCompanies(token).then((companies) => {
      if (companies.length === 0) {
        router.replace("/app/companies/new");
        return;
      }
      const first = companies[0];
      if (first) {
        router.replace(`/app/companies/${first.id}`);
      }
    });
  }, [router]);

  return <p className="text-sm text-zinc-500">Loading your company…</p>;
}
