"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, type ReactNode, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import { getToken } from "@/lib/auth";

export default function NewCompanyPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [mission, setMission] = useState("");
  const [industry, setIndustry] = useState("Technology");
  const [logoUrl, setLogoUrl] = useState("");
  const [timezone, setTimezone] = useState("UTC");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    setPending(true);
    setError(null);
    try {
      const payload = {
        name,
        description,
        mission,
        industry,
        settings: { timezone, locale: "en-US", work_days: ["mon", "tue", "wed", "thu", "fri"] },
        ...(logoUrl.trim() ? { logo_url: logoUrl.trim() } : {}),
      };
      const company = await api.createCompany(token, payload);
      router.push(`/app/companies/${company.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to create company.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <p className="text-xs uppercase tracking-[0.2em] text-cyan-300/80">Step 2</p>
      <h1 className="mt-2 text-3xl font-semibold">Create your company</h1>
      <p className="mt-2 text-sm text-zinc-400">Name, mission, industry, logo, and settings. Agents come in Phase 2.</p>
      <Card className="mt-8 p-6">
        <form className="space-y-4" onSubmit={onSubmit}>
          <Field label="Company name" htmlFor="name">
            <Input id="name" value={name} onChange={(e) => setName(e.target.value)} required minLength={2} />
          </Field>
          <Field label="Description" htmlFor="description">
            <Textarea id="description" value={description} onChange={(e) => setDescription(e.target.value)} />
          </Field>
          <Field label="Mission" htmlFor="mission">
            <Textarea id="mission" value={mission} onChange={(e) => setMission(e.target.value)} />
          </Field>
          <Field label="Industry" htmlFor="industry">
            <Input id="industry" value={industry} onChange={(e) => setIndustry(e.target.value)} />
          </Field>
          <Field label="Logo URL" htmlFor="logo">
            <Input
              id="logo"
              type="url"
              placeholder="https://…"
              value={logoUrl}
              onChange={(e) => setLogoUrl(e.target.value)}
            />
          </Field>
          <Field label="Timezone" htmlFor="tz">
            <Input id="tz" value={timezone} onChange={(e) => setTimezone(e.target.value)} />
          </Field>
          {error ? <p className="text-sm text-rose-400">{error}</p> : null}
          <Button disabled={pending} type="submit">
            {pending ? "Creating…" : "Create company"}
          </Button>
        </form>
      </Card>
    </div>
  );
}

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
    </div>
  );
}
