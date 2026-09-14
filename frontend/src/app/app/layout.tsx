"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useEffect, useSyncExternalStore } from "react";
import { clearToken, readServerTokenSnapshot, readTokenSnapshot, subscribeToken } from "@/lib/auth";
import { cn } from "@/lib/utils";

const upcoming = [
  { href: "#", label: "Agents", disabled: true },
  { href: "#", label: "Tasks", disabled: true },
  { href: "#", label: "Projects", disabled: true },
  { href: "#", label: "Memory", disabled: true },
  { href: "#", label: "Activity", disabled: true },
  { href: "#", label: "Office", disabled: true },
  { href: "#", label: "Analytics", disabled: true },
];

export default function AppLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const token = useSyncExternalStore(subscribeToken, readTokenSnapshot, readServerTokenSnapshot);

  useEffect(() => {
    if (!token) {
      router.replace("/login");
    }
  }, [router, token]);

  if (!token) {
    return <div className="min-h-screen bg-background" />;
  }

  return (
    <div className="mesh flex min-h-screen">
      <aside className="hidden w-60 shrink-0 border-r border-white/10 bg-zinc-950/50 p-5 md:block">
        <Link href="/app" className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-cyan-400" />
          <span className="font-semibold">Fellows</span>
        </Link>
        <nav className="mt-8 space-y-1 text-sm">
          <NavLink href="/app" active={pathname === "/app" || pathname.startsWith("/app/companies")}>
            Company
          </NavLink>
          {upcoming.map((item) => (
            <span
              key={item.label}
              className="flex items-center justify-between rounded-lg px-3 py-2 text-zinc-600"
            >
              {item.label}
              <span className="text-[10px] uppercase tracking-wide">Soon</span>
            </span>
          ))}
        </nav>
        <button
          type="button"
          className="mt-10 text-xs text-zinc-500 hover:text-zinc-300"
          onClick={() => {
            clearToken();
            router.push("/");
          }}
        >
          Sign out
        </button>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-white/10 px-6 py-4 md:hidden">
          <span className="font-semibold">Fellows</span>
          <button
            type="button"
            className="text-xs text-zinc-400"
            onClick={() => {
              clearToken();
              router.push("/");
            }}
          >
            Sign out
          </button>
        </header>
        <main className="flex-1 px-6 py-8">{children}</main>
      </div>
    </div>
  );
}

function NavLink({
  href,
  active,
  children,
}: {
  href: string;
  active: boolean;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "block rounded-lg px-3 py-2",
        active ? "bg-white/10 text-white" : "text-zinc-400 hover:bg-white/5 hover:text-white",
      )}
    >
      {children}
    </Link>
  );
}
