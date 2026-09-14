"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import { setToken } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      const result = await api.login(email, password);
      setToken(result.access_token);
      router.push("/app");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to log in.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="mesh flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-md p-8">
        <p className="text-xs uppercase tracking-[0.2em] text-cyan-300/80">Fellows</p>
        <h1 className="mt-2 text-2xl font-semibold">Welcome back</h1>
        <p className="mt-2 text-sm text-zinc-400">Log in to your AI company.</p>
        <form className="mt-8 space-y-4" onSubmit={onSubmit}>
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error ? <p className="text-sm text-rose-400">{error}</p> : null}
          <Button className="w-full" disabled={pending} type="submit">
            {pending ? "Signing in…" : "Log in"}
          </Button>
        </form>
        <p className="mt-6 text-sm text-zinc-500">
          New here?{" "}
          <Link className="text-cyan-300 hover:underline" href="/register">
            Create an account
          </Link>
        </p>
      </Card>
    </div>
  );
}
