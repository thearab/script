import { Sparkles } from "lucide-react";

const HomePage = () => {
  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <section className="max-w-2xl space-y-6 rounded-3xl border border-slate-200 bg-white p-10 shadow-sm">
        <div className="flex items-center gap-3 text-slate-900">
          <Sparkles className="h-7 w-7 text-indigo-500" />
          <h1 className="text-3xl font-semibold">Ghurfati</h1>
        </div>
        <p className="text-lg text-slate-600">
          Upload a room photo, apply AI styling, and get IKEA-ready product matches in minutes.
        </p>
        <div className="flex flex-wrap gap-3 text-sm text-slate-500">
          <span className="rounded-full bg-slate-100 px-3 py-1">Next.js 14</span>
          <span className="rounded-full bg-slate-100 px-3 py-1">FastAPI</span>
          <span className="rounded-full bg-slate-100 px-3 py-1">Supabase + pgvector</span>
        </div>
      </section>
    </main>
  );
};

export default HomePage;
