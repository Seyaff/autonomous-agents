"use client";

import Link from "next/link";
import {
  ArrowRight,
  CheckCircle2,
  ChefHat,
  MessageSquare,
  Sparkles,
  TrendingUp,
  Zap,
  ShieldCheck,
  Smartphone,
  ExternalLink,
  Clock,
  Flame,
  Radio,
} from "lucide-react";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#09090b] text-[#f4f4f5] selection:bg-emerald-500/20 selection:text-emerald-300">
      {/* Ambient background glow */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        <div className="absolute -top-40 left-1/2 -translate-x-1/2 w-[800px] h-[500px] bg-emerald-950/20 blur-[140px] rounded-full" />
        <div className="absolute top-[600px] -left-40 w-[600px] h-[400px] bg-zinc-900/40 blur-[120px] rounded-full" />
      </div>

      {/* Navigation */}
      <header className="relative z-10 border-b border-white/[0.07] bg-[#09090b]/80 backdrop-blur-md sticky top-0">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold">
              <ChefHat className="h-5 w-5" />
            </div>
            <div>
              <span className="font-semibold tracking-tight text-white text-base">
                Pakhtun Dera AI
              </span>
              <span className="ml-2 px-1.5 py-0.5 rounded text-[10px] font-mono tracking-wider uppercase bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                v2.0
              </span>
            </div>
          </div>

          <nav className="hidden md:flex items-center gap-8 text-xs font-medium text-zinc-400">
            <a href="#features" className="hover:text-white transition-colors">
              Platform Features
            </a>
            <a href="#dispatch" className="hover:text-white transition-colors">
              Kitchen Dispatch
            </a>
            <a href="#growth" className="hover:text-white transition-colors">
              Viral Growth Loops
            </a>
            <a href="#embedded" className="hover:text-white transition-colors">
              Meta 1-Click Signup
            </a>
          </nav>

          <div className="flex items-center gap-3">
            <Link
              href="/kds"
              className="text-xs font-medium px-3.5 py-1.5 rounded-lg text-zinc-300 hover:text-white hover:bg-white/[0.05] border border-white/[0.08] transition-all hidden sm:flex items-center gap-1.5"
            >
              <Radio className="h-3.5 w-3.5 text-emerald-400 animate-pulse" />
              Live KDS
            </Link>
            <Link
              href="/onboarding"
              className="text-xs font-medium px-4 py-1.5 rounded-lg bg-white text-black hover:bg-zinc-200 transition-all flex items-center gap-1.5 shadow-[0_0_20px_rgba(255,255,255,0.15)]"
            >
              Launch Onboarding
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </header>

      <main className="relative z-10">
        {/* Hero Section */}
        <section className="pt-24 pb-20 px-6 max-w-7xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium mb-8">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-ping" />
            Meta WhatsApp Cloud API v21.0 Certified • Zero Commission
          </div>

          <h1 className="text-4xl sm:text-6xl md:text-7xl font-semibold tracking-tight text-white max-w-4xl mx-auto leading-[1.08]">
            Autonomous Restaurant Operations{" "}
            <span className="text-transparent bg-clip-text bg-gradient-to-b from-white via-zinc-200 to-zinc-500">
              over WhatsApp.
            </span>
          </h1>

          <p className="mt-6 text-base sm:text-lg text-zinc-400 max-w-2xl mx-auto leading-relaxed font-normal">
            Natural Pakistani Roman Urdu ordering agent, dual-channel kitchen dispatch slips, and autonomous post-delivery viral growth loops. Live in 90 seconds.
          </p>

          <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
            <Link
              href="/onboarding"
              className="h-12 px-7 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-sm transition-all flex items-center gap-2 shadow-[0_0_25px_rgba(16,185,129,0.3)]"
            >
              Start 90-Sec Onboarding
              <ArrowRight className="h-4 w-4" />
            </Link>

            <Link
              href="/kds"
              className="h-12 px-7 rounded-xl bg-[#121215] hover:bg-[#18181d] text-zinc-200 font-medium text-sm border border-white/[0.1] transition-all flex items-center gap-2"
            >
              <ChefHat className="h-4 w-4 text-emerald-400" />
              Kitchen Display (KDS)
            </Link>

            <Link
              href="/dashboard"
              className="h-12 px-6 rounded-xl bg-transparent hover:bg-white/[0.05] text-zinc-400 hover:text-white text-sm transition-all flex items-center gap-1.5"
            >
              Owner Dashboard
              <ExternalLink className="h-3.5 w-3.5" />
            </Link>
          </div>

          {/* Social Proof Numbers */}
          <div className="mt-16 grid grid-cols-2 sm:grid-cols-4 gap-6 max-w-4xl mx-auto pt-10 border-t border-white/[0.07]">
            <div className="text-left">
              <div className="text-2xl sm:text-3xl font-semibold text-white font-mono tracking-tight">
                0%
              </div>
              <div className="text-xs text-zinc-500 mt-1">Platform Commission</div>
            </div>
            <div className="text-left">
              <div className="text-2xl sm:text-3xl font-semibold text-emerald-400 font-mono tracking-tight">
                &lt; 1.2s
              </div>
              <div className="text-xs text-zinc-500 mt-1">Urdu Agent Latency</div>
            </div>
            <div className="text-left">
              <div className="text-2xl sm:text-3xl font-semibold text-white font-mono tracking-tight">
                2.4x
              </div>
              <div className="text-xs text-zinc-500 mt-1">Repeat Diner Frequency</div>
            </div>
            <div className="text-left">
              <div className="text-2xl sm:text-3xl font-semibold text-white font-mono tracking-tight">
                1-Click
              </div>
              <div className="text-xs text-zinc-500 mt-1">Meta Embedded Signup</div>
            </div>
          </div>
        </section>

        {/* Live Side-by-Side Dual Engine Preview */}
        <section id="dispatch" className="py-16 px-6 max-w-7xl mx-auto">
          <div className="text-center mb-12">
            <span className="text-xs uppercase tracking-widest text-emerald-400 font-mono">
              Live Interactive Simulation
            </span>
            <h2 className="text-2xl sm:text-4xl font-semibold text-white mt-2">
              From WhatsApp Message to Sizzling Karahi
            </h2>
            <p className="text-sm text-zinc-400 mt-2 max-w-xl mx-auto">
              How the autonomous customer host and real-time kitchen dispatch operate simultaneously without human cashier intervention.
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-stretch">
            {/* Left: WhatsApp Customer Simulation */}
            <div className="rounded-2xl bg-[#0c1317] border border-white/[0.08] p-6 shadow-2xl flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between border-b border-white/[0.08] pb-4 mb-4">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-full bg-emerald-600/30 border border-emerald-500/40 flex items-center justify-center font-bold text-emerald-300">
                      DP
                    </div>
                    <div>
                      <div className="text-sm font-medium text-white flex items-center gap-2">
                        Da Pakhtun Dera
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                      </div>
                      <div className="text-xs text-emerald-400/80">Online • Autonomous Host</div>
                    </div>
                  </div>
                  <span className="text-[11px] font-mono text-zinc-500">Customer View</span>
                </div>

                {/* Chat Bubbles */}
                <div className="space-y-3.5 text-xs">
                  <div className="flex justify-end">
                    <div className="bg-[#005c4b] text-white p-3 rounded-xl rounded-tr-none max-w-[80%] shadow">
                      Assalam-o-Alaikum! Menu dikhao please.
                      <div className="text-[9px] text-zinc-300 text-right mt-1 font-mono">09:42 PM ✓✓</div>
                    </div>
                  </div>

                  <div className="flex justify-start">
                    <div className="bg-[#202c33] text-zinc-200 p-3 rounded-xl rounded-tl-none max-w-[85%] border border-white/[0.05] shadow">
                      <p className="font-medium text-emerald-300">Walaikum Assalam! Khushamdeed Da Pakhtun Dera mein.</p>
                      <p className="mt-1">Hamare aaj ke fresh specials:</p>
                      <ul className="mt-1.5 space-y-1 font-mono text-[11px] text-zinc-300">
                        <li>• Shinwari Mutton Karahi — Rs. 2,400 (Full)</li>
                        <li>• Peshawari Chapli Kabab — Rs. 650</li>
                        <li>• Kabuli Pulao — Rs. 850</li>
                        <li>• Roghani Naan — Rs. 80</li>
                      </ul>
                      <p className="mt-1.5 text-zinc-400">Aap kis dish se shuru karna chahenge?</p>
                      <div className="text-[9px] text-zinc-400 text-right mt-1 font-mono">09:42 PM</div>
                    </div>
                  </div>

                  <div className="flex justify-end">
                    <div className="bg-[#005c4b] text-white p-3 rounded-xl rounded-tr-none max-w-[80%] shadow">
                      1 Shinwari Mutton Karahi Full aur 4 Roghani Naan bhej dein. Address: House 12, Ring Road, Kohat.
                      <div className="text-[9px] text-zinc-300 text-right mt-1 font-mono">09:43 PM ✓✓</div>
                    </div>
                  </div>

                  <div className="flex justify-start">
                    <div className="bg-[#202c33] text-zinc-200 p-3 rounded-xl rounded-tl-none max-w-[85%] border border-emerald-500/20 shadow">
                      <p className="font-medium text-emerald-300">Zabardast! Order #PK-7701 confirm ho gaya hai 🎉</p>
                      <div className="mt-2 p-2 rounded bg-black/30 border border-white/[0.05] font-mono text-[11px]">
                        <div>• 1x Shinwari Mutton Karahi (Full) = Rs. 2,400</div>
                        <div>• 4x Roghani Naan = Rs. 320</div>
                        <div className="border-t border-white/10 mt-1 pt-1 font-bold text-white">
                          Total: Rs. 2,720 (Cash on Delivery)
                        </div>
                      </div>
                      <p className="mt-2 text-zinc-300">Kitchen ko slip bhej di gayi hai. Ready hotay hi aapko update milegi!</p>
                      <div className="text-[9px] text-zinc-400 text-right mt-1 font-mono">09:43 PM</div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-white/[0.05] text-[11px] text-zinc-500 flex items-center justify-between">
                <span>Natural Pakistani Roman Urdu Engine</span>
                <span className="text-emerald-400 font-mono">0 Gatekeeping</span>
              </div>
            </div>

            {/* Right: Instant Kitchen Slip + KDS View */}
            <div className="rounded-2xl bg-[#121215] border border-white/[0.08] p-6 shadow-2xl flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between border-b border-white/[0.08] pb-4 mb-4">
                  <div className="flex items-center gap-2.5">
                    <div className="h-2.5 w-2.5 rounded-full bg-amber-400 animate-pulse" />
                    <span className="text-sm font-semibold text-white">Dual Kitchen Dispatch</span>
                  </div>
                  <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-amber-500/10 text-amber-400 border border-amber-500/20">
                    Auto-Dispatched in 400ms
                  </span>
                </div>

                {/* Formatted Kitchen Slip Preview */}
                <div className="p-4 rounded-xl bg-[#09090b] border border-white/[0.08] font-mono text-xs text-zinc-300 leading-relaxed shadow-inner">
                  <div className="text-amber-400 font-bold flex items-center justify-between">
                    <span>🔔 KITCHEN TICKET #PK-7701</span>
                    <span className="text-zinc-500 text-[10px]">TIME: 09:43 PM</span>
                  </div>
                  <div className="text-zinc-600 my-1">━━━━━━━━━━━━━━━━━━━━━━━━━━━━</div>
                  <div className="text-[11px] text-zinc-400">
                    📍 Delivery: House 12, Ring Road, Kohat
                  </div>
                  <div className="text-zinc-600 my-1">━━━━━━━━━━━━━━━━━━━━━━━━━━━━</div>
                  <div className="space-y-1 my-2 text-white">
                    <div className="font-semibold">• 1x Shinwari Mutton Karahi (Full)</div>
                    <div className="text-[11px] text-zinc-400 pl-3">↳ Special: Medium spice, fresh dum</div>
                    <div className="font-semibold">• 4x Roghani Naan</div>
                    <div className="text-[11px] text-zinc-400 pl-3">↳ Hot & crisp from tandoor</div>
                  </div>
                  <div className="text-zinc-600 my-1">━━━━━━━━━━━━━━━━━━━━━━━━━━━━</div>
                  <div className="flex items-center justify-between text-emerald-400 font-bold">
                    <span>Total Amount: Rs. 2,720</span>
                    <span className="text-zinc-400 font-normal text-[10px]">(COD)</span>
                  </div>
                </div>

                {/* KDS Live State Simulator */}
                <div className="mt-4 p-3 rounded-xl bg-white/[0.02] border border-white/[0.06] flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Clock className="h-4 w-4 text-amber-400" />
                    <div>
                      <div className="text-xs font-medium text-white">Status: Preparing</div>
                      <div className="text-[10px] text-zinc-500 font-mono">Elapsed: 04:12 min</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button className="px-3 py-1 rounded text-xs font-medium bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30 transition-all">
                      Mark Ready
                    </button>
                  </div>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-white/[0.05] text-[11px] text-zinc-500 flex items-center justify-between">
                <span>Sent to Staff WhatsApp + WebSocket KDS</span>
                <span className="text-amber-400 font-mono">Bi-Directional Sync</span>
              </div>
            </div>
          </div>
        </section>

        {/* Feature Grid: 4 Core Pillars */}
        <section id="features" className="py-20 px-6 max-w-7xl mx-auto border-t border-white/[0.07]">
          <div className="text-center mb-16">
            <span className="text-xs uppercase tracking-widest text-emerald-400 font-mono">
              Core Architecture
            </span>
            <h2 className="text-3xl sm:text-4xl font-semibold text-white mt-2">
              Engineered for Real Restaurant Realities
            </h2>
            <p className="text-sm text-zinc-400 mt-2 max-w-xl mx-auto">
              No complicated apps for customers to download. Zero awkward chatbot loops.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {/* Feature 1 */}
            <div className="p-6 rounded-2xl bg-[#121215] border border-white/[0.08] hover:border-emerald-500/30 transition-all group">
              <div className="h-10 w-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mb-5">
                <MessageSquare className="h-5 w-5" />
              </div>
              <h3 className="text-base font-medium text-white group-hover:text-emerald-300 transition-colors">
                Pakistani Roman Urdu Host
              </h3>
              <p className="mt-2 text-xs text-zinc-400 leading-relaxed">
                Speaks natural, polite Pakistani Roman Urdu. Never gatekeeps the menu, quotes exact Rs. prices from DB, and handles active order recall seamlessly.
              </p>
            </div>

            {/* Feature 2 */}
            <div className="p-6 rounded-2xl bg-[#121215] border border-white/[0.08] hover:border-emerald-500/30 transition-all group">
              <div className="h-10 w-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 mb-5">
                <ChefHat className="h-5 w-5" />
              </div>
              <h3 className="text-base font-medium text-white group-hover:text-amber-300 transition-colors">
                Dual Kitchen Dispatch
              </h3>
              <p className="mt-2 text-xs text-zinc-400 leading-relaxed">
                Chefs receive monospaced WhatsApp tickets on their phones, while kitchen tablets stream live orders via WebSockets with real-time sound chimes.
              </p>
            </div>

            {/* Feature 3 */}
            <div id="growth" className="p-6 rounded-2xl bg-[#121215] border border-white/[0.08] hover:border-emerald-500/30 transition-all group">
              <div className="h-10 w-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mb-5">
                <TrendingUp className="h-5 w-5" />
              </div>
              <h3 className="text-base font-medium text-white group-hover:text-emerald-300 transition-colors">
                Autonomous Viral Loops
              </h3>
              <p className="mt-2 text-xs text-zinc-400 leading-relaxed">
                Automated 45-min post-delivery prompt for Instagram Story / WhatsApp Status tags in exchange for free Kahwa. Plus 6–7 day win-back re-engagement.
              </p>
            </div>

            {/* Feature 4 */}
            <div id="embedded" className="p-6 rounded-2xl bg-[#121215] border border-white/[0.08] hover:border-emerald-500/30 transition-all group">
              <div className="h-10 w-10 rounded-xl bg-zinc-800/60 border border-white/[0.1] flex items-center justify-center text-zinc-200 mb-5">
                <Zap className="h-5 w-5" />
              </div>
              <h3 className="text-base font-medium text-white group-hover:text-zinc-200 transition-colors">
                1-Click Meta Embedded Signup
              </h3>
              <p className="mt-2 text-xs text-zinc-400 leading-relaxed">
                Zero developer consoles or manual token copy-pasting. Owners connect their WhatsApp Business in 90 seconds via Meta’s official co-branded modal.
              </p>
            </div>
          </div>
        </section>

        {/* Viral Marketing Highlight Banner */}
        <section className="py-16 px-6 max-w-7xl mx-auto">
          <div className="rounded-3xl bg-gradient-to-b from-[#18181d] to-[#101014] border border-white/[0.1] p-8 sm:p-12 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
            <div className="relative z-10 max-w-2xl">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono mb-4">
                <Flame className="h-3.5 w-3.5" />
                Zero Ad-Spend Customer Acquisition
              </div>
              <h3 className="text-2xl sm:text-3xl font-semibold text-white">
                Turn Every Delivered Order into a Viral Social Post
              </h3>
              <p className="mt-3 text-sm text-zinc-400 leading-relaxed">
                45 minutes after delivery, the agent politely asks diners to share a picture of their meal on their Instagram Story or WhatsApp Status tagging your restaurant. In return, they receive a complimentary Roghani Naan or Peshawari Kahwa on their next order.
              </p>
              <div className="mt-6 flex flex-wrap gap-4">
                <div className="flex items-center gap-2 text-xs font-medium text-zinc-300">
                  <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                  Free Local Word-of-Mouth
                </div>
                <div className="flex items-center gap-2 text-xs font-medium text-zinc-300">
                  <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                  6–7 Day Habit Win-Back Cron
                </div>
                <div className="flex items-center gap-2 text-xs font-medium text-zinc-300">
                  <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                  Friday 4:30 PM Family Feast Nudges
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* CTA Banner */}
        <section className="py-20 px-6 max-w-4xl mx-auto text-center">
          <h2 className="text-3xl sm:text-4xl font-semibold text-white">
            Ready to deploy for your restaurant?
          </h2>
          <p className="mt-3 text-sm text-zinc-400 max-w-md mx-auto">
            Test the live pilot for Da Pakhtun Dera or onboard a new branch in less than two minutes.
          </p>
          <div className="mt-8 flex justify-center gap-4">
            <Link
              href="/onboarding"
              className="h-12 px-8 rounded-xl bg-white text-black hover:bg-zinc-200 font-medium text-sm transition-all flex items-center gap-2 shadow-[0_0_30px_rgba(255,255,255,0.2)]"
            >
              Start Step-by-Step Onboarding
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-white/[0.07] bg-[#09090b] py-8 px-6 text-xs text-zinc-500">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            <span>FastAPI + LangGraph + Next.js 15 • Active Pilot: Da Pakhtun Dera</span>
          </div>
          <div className="flex items-center gap-6">
            <Link href="/onboarding" className="hover:text-zinc-300 transition-colors">
              Onboarding
            </Link>
            <Link href="/kds" className="hover:text-zinc-300 transition-colors">
              Kitchen Display
            </Link>
            <Link href="/dashboard" className="hover:text-zinc-300 transition-colors">
              Dashboard
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
