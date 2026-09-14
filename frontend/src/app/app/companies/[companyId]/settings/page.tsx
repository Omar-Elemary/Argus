"use client";

import { useParams, useRouter } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { Company } from "@/lib/types";

export default function CompanySettingsPage() {
  const params = useParams<{ companyId: string }>();
  const router = useRouter();
  const [company, setCompany] = useState<Company | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    void api
      .getOverview(token, params.companyId)
      .then((overview) => setCompany(overview.company))
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : "Unable to load settings.");
      });
  }, [params.companyId, router]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!company) return;
    const token = getToken();
    if (!token) return;
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError(null);
    try {
      const updated = await api.updateCompany(token, company.id, {
        name: String(form.get("name") ?? ""),
        description: String(form.get("description") ?? ""),
        mission: String(form.get("mission") ?? ""),
        industry: String(form.get("industry") ?? ""),
      });
      setCompany(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to save.");
    } finally {
      setPending(false);
    }
  }

  if (!company && !error) {
    return <p className="text-sm text-zinc-500">Loading settings…</p>;
  }
  if (!company) {
    return <p className="text-sm text-rose-400">{error}</p>;
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-3xl font-semibold">Company settings</h1>
      <Card className="mt-8 p-6">
        <form className="space-y-4" onSubmit={onSubmit}>
          <div className="space-y-2">
            <Label htmlFor="name">Name</Label>
            <Input id="name" name="name" defaultValue={company.name} required />
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea id="description" name="description" defaultValue={company.description} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="mission">Mission</Label>
            <Textarea id="mission" name="mission" defaultValue={company.mission} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="industry">Industry</Label>
            <Input id="industry" name="industry" defaultValue={company.industry} />
          </div>
          {error ? <p className="text-sm text-rose-400">{error}</p> : null}
          <Button disabled={pending} type="submit">
            {pending ? "Saving…" : "Save changes"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
