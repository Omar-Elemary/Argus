"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { CompanyOverview } from "@/lib/types";

export default function CompanyDashboardPage() {
  const params = useParams<{ companyId: string }>();
  const router = useRouter();
  const [overview, setOverview] = useState<CompanyOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    void api
      .getOverview(token, params.companyId)
      .then(setOverview)
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : "Unable to load company.");
      });
  }, [params.companyId, router]);

  if (error) {
    return <p className="text-sm text-rose-400">{error}</p>;
  }
  if (!overview) {
    return <p className="text-sm text-zinc-500">Loading overview…</p>;
  }

  const { company, members, recent_events: events } = overview;
  const initials = company.name.slice(0, 2).toUpperCase();

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          {company.logo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={company.logo_url} alt="" className="h-14 w-14 rounded-2xl object-cover ring-1 ring-white/10" />
          ) : (
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-400 to-violet-500 text-lg font-semibold text-zinc-950">
              {initials}
            </div>
          )}
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-zinc-500">{company.industry || "Company"}</p>
            <h1 className="text-3xl font-semibold">{company.name}</h1>
            <p className="mt-1 max-w-xl text-sm text-zinc-400">{company.mission || company.description}</p>
          </div>
        </div>
        <Link
          href={`/app/companies/${company.id}/settings`}
          className="rounded-lg border border-white/10 px-3 py-2 text-sm text-zinc-300 hover:bg-white/5"
        >
          Settings
        </Link>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Stat label="Members" value={String(members.length)} hint="From memberships" />
        <Stat label="AI employees" value="—" hint="Agent hiring is Phase 2" />
        <Stat label="Open tasks" value="—" hint="Tasks are Phase 3" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-6">
          <h2 className="text-sm font-medium text-zinc-300">Company</h2>
          <dl className="mt-4 space-y-3 text-sm">
            <Row label="Description" value={company.description || "—"} />
            <Row label="Mission" value={company.mission || "—"} />
            <Row label="Industry" value={company.industry || "—"} />
            <Row
              label="Timezone"
              value={
                typeof company.settings === "object" &&
                company.settings !== null &&
                "timezone" in company.settings
                  ? String(company.settings.timezone)
                  : "UTC"
              }
            />
          </dl>
        </Card>
        <Card className="p-6">
          <h2 className="text-sm font-medium text-zinc-300">Activity</h2>
          <p className="mt-1 text-xs text-zinc-500">Real events only. Nothing is simulated.</p>
          <ul className="mt-4 space-y-3">
            {events.length === 0 ? (
              <li className="text-sm text-zinc-500">No events yet.</li>
            ) : (
              events.map((event) => (
                <li key={event.id} className="text-sm">
                  <span className="font-mono text-xs text-cyan-300/80">{event.event_type}</span>
                  <p className="text-zinc-400">
                    {new Date(event.timestamp).toLocaleString()} ·{" "}
                    {typeof event.payload.name === "string" ? event.payload.name : company.name}
                  </p>
                </li>
              ))
            )}
          </ul>
        </Card>
      </div>

      <Card className="p-6">
        <h2 className="text-sm font-medium text-zinc-300">Team</h2>
        <ul className="mt-4 divide-y divide-white/5">
          {members.map((member) => (
            <li key={member.user_id} className="flex items-center justify-between py-3 text-sm">
              <div>
                <p>{member.full_name}</p>
                <p className="text-zinc-500">{member.email}</p>
              </div>
              <span className="rounded-full bg-white/5 px-2 py-1 text-xs capitalize text-zinc-300">
                {member.role}
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <Card className="p-5">
      <p className="text-xs uppercase tracking-wide text-zinc-500">{label}</p>
      <p className="mt-2 text-3xl font-semibold">{value}</p>
      <p className="mt-1 text-xs text-zinc-500">{hint}</p>
    </Card>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-zinc-500">{label}</dt>
      <dd className="text-zinc-200">{value}</dd>
    </div>
  );
}
