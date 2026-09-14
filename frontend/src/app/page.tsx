import Link from "next/link";
import { OfficeIllustration } from "@/components/office-illustration";

export default function LandingPage() {
  return (
    <div className="mesh min-h-screen">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-6">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-cyan-400 shadow-[0_0_16px_rgba(34,211,238,0.8)]" />
          <span className="text-sm font-semibold tracking-wide">Fellows</span>
        </div>
        <nav className="flex items-center gap-3">
          <Link href="/login" className="text-sm text-zinc-300 hover:text-white">
            Log in
          </Link>
          <Link
            href="/register"
            className="rounded-lg bg-cyan-400 px-3 py-2 text-sm font-medium text-zinc-950 hover:bg-cyan-300"
          >
            Create your company
          </Link>
        </nav>
      </header>

      <main className="mx-auto grid w-full max-w-6xl gap-12 px-6 pb-24 pt-10 lg:grid-cols-2 lg:items-center">
        <div>
          <p className="text-xs uppercase tracking-[0.28em] text-cyan-300/80">AI company OS</p>
          <h1 className="mt-4 text-5xl font-semibold tracking-tight text-white sm:text-6xl">
            Build Your AI Company.
          </h1>
          <p className="mt-6 max-w-md text-lg leading-8 text-zinc-400">
            Create AI employees.
            <br />
            Give them work.
            <br />
            Watch them build.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/register"
              className="rounded-lg bg-cyan-400 px-5 py-3 text-sm font-semibold text-zinc-950 hover:bg-cyan-300"
            >
              Create Your Company
            </Link>
            <button
              type="button"
              disabled
              className="rounded-lg border border-white/10 px-5 py-3 text-sm text-zinc-500"
              title="Demo seed ships later — it will be real ACME AI data, not a simulation."
            >
              Explore Demo
            </button>
          </div>
        </div>
        <OfficeIllustration />
      </main>
    </div>
  );
}
