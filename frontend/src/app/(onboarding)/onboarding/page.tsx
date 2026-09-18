"use client";

import { useState } from "react";
import Link from "next/link";
import {
  ChefHat,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  Smartphone,
  Check,
  Send,
  Sparkles,
  ExternalLink,
  ShieldCheck,
  Radio,
  QrCode,
} from "lucide-react";
import {
  useStartOnboarding,
  useUpdateIdentity,
  useUpdateMenu,
  useConnectWhatsApp,
  useSendKitchenTestSlip,
  useCompleteOnboarding,
} from "@/hooks/use-onboarding";
import type { MenuItem } from "@/types";

export default function OnboardingPage() {
  const [step, setStep] = useState<number>(1);
  const [tenantId, setTenantId] = useState<string>("");
  const [restaurantName, setRestaurantName] = useState("Da Pakhtun Dera");
  const [cuisine, setCuisine] = useState("Shinwari BBQ & Traditional");
  const [city, setCity] = useState("Kohat");
  const [address, setAddress] = useState("Ring Road Near Highway, Kohat");
  const [openingHours, setOpeningHours] = useState("12:00 PM – 01:00 AM");
  const [kitchenPhone, setKitchenPhone] = useState("923417268523");

  // Menu items state
  const [menuItems, setMenuItems] = useState<MenuItem[]>([
    { name: "Shinwari Mutton Karahi (Full)", category: "Karahi Specials", price: 2400, is_available: true },
    { name: "Peshawari Chapli Kabab", category: "BBQ & Kababs", price: 650, is_available: true },
    { name: "Kabuli Pulao", category: "Rice", price: 850, is_available: true },
    { name: "Roghani Naan", category: "Tandoor", price: 80, is_available: true },
    { name: "Peshawari Kahwa", category: "Beverages", price: 120, is_available: true },
  ]);

  // WhatsApp setup state
  const [isSandboxMode, setIsSandboxMode] = useState(false);
  const [phoneNumberId, setPhoneNumberId] = useState("1251071574764683");
  const [wabaId, setWabaId] = useState("1251071574764683");
  const [accessToken, setAccessToken] = useState("");
  const [whatsappConnected, setWhatsappConnected] = useState(false);

  // Test ticket state
  const [testSent, setTestSent] = useState(false);
  const [liveWaLink, setLiveWaLink] = useState("");

  // Mutations
  const startMutation = useStartOnboarding();
  const identityMutation = useUpdateIdentity(tenantId);
  const menuMutation = useUpdateMenu(tenantId);
  const whatsappMutation = useConnectWhatsApp(tenantId);
  const kitchenMutation = useSendKitchenTestSlip(tenantId);
  const completeMutation = useCompleteOnboarding(tenantId);

  // Step 1: Save Identity
  const handleSaveIdentity = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      let activeId = tenantId;
      if (!activeId) {
        const startRes = await startMutation.mutateAsync({
          name: restaurantName,
          currency: "PKR",
        });
        activeId = startRes.tenant_id;
        setTenantId(activeId);
      }

      await identityMutation.mutateAsync({
        name: restaurantName,
        cuisine,
        city,
        address,
        opening_hours: openingHours,
        kitchen_phone: kitchenPhone,
      });

      setStep(2);
    } catch (err: any) {
      alert(`Error saving identity: ${err.message}`);
    }
  };

  // Step 2: Save Menu
  const handleSaveMenu = async () => {
    try {
      await menuMutation.mutateAsync(menuItems);
      setStep(3);
    } catch (err: any) {
      alert(`Error saving menu: ${err.message}`);
    }
  };

  // Step 3: Connect WhatsApp
  const handleConnectWhatsApp = async () => {
    try {
      await whatsappMutation.mutateAsync({
        phone_number_id: phoneNumberId || "1251071574764683",
        waba_id: wabaId || "1251071574764683",
        access_token: accessToken || undefined,
        display_phone_number: kitchenPhone,
      });
      setWhatsappConnected(true);
      setStep(4);
    } catch (err: any) {
      alert(`Error connecting WhatsApp: ${err.message}`);
    }
  };

  // Step 4: Send Test Ticket
  const handleSendTestTicket = async () => {
    try {
      await kitchenMutation.mutateAsync(kitchenPhone);
      setTestSent(true);
      setTimeout(() => setStep(5), 1500);
    } catch (err: any) {
      alert(`Error sending test ticket: ${err.message}`);
    }
  };

  // Step 5: Complete & Launch
  const handleComplete = async () => {
    try {
      const res = await completeMutation.mutateAsync();
      setLiveWaLink(res.whatsapp_link || `https://wa.me/${kitchenPhone}?text=Assalam-o-Alaikum`);
    } catch (err: any) {
      setLiveWaLink(`https://wa.me/${kitchenPhone}?text=Assalam-o-Alaikum`);
    }
  };

  const stepsHeader = [
    { num: 1, title: "Identity" },
    { num: 2, title: "Menu" },
    { num: 3, title: "WhatsApp" },
    { num: 4, title: "Kitchen Test" },
    { num: 5, title: "Launch" },
  ];

  return (
    <div className="min-h-screen bg-[#09090b] text-[#f4f4f5] flex flex-col justify-between selection:bg-emerald-500/20 selection:text-emerald-300">
      {/* Top Header */}
      <header className="border-b border-white/[0.07] bg-[#09090b]/80 backdrop-blur-md px-6 py-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold">
              <ChefHat className="h-4 w-4" />
            </div>
            <span className="font-semibold text-sm tracking-tight text-white">
              Restaurant Setup Wizard
            </span>
          </Link>

          <span className="text-xs text-zinc-500 font-mono">
            Linear Luxury Onboarding
          </span>
        </div>
      </header>

      {/* Progress Bar & Stepper */}
      <div className="max-w-3xl mx-auto w-full px-6 pt-10">
        <div className="flex items-center justify-between relative">
          <div className="absolute left-0 top-1/2 -translate-y-1/2 h-[1px] w-full bg-zinc-800 -z-0" />
          <div
            className="absolute left-0 top-1/2 -translate-y-1/2 h-[1px] bg-emerald-500 transition-all duration-500 -z-0"
            style={{ width: `${((step - 1) / 4) * 100}%` }}
          />

          {stepsHeader.map((s) => (
            <div
              key={s.num}
              className="relative z-10 flex flex-col items-center gap-1.5 bg-[#09090b] px-2"
            >
              <div
                className={`h-8 w-8 rounded-full flex items-center justify-center text-xs font-semibold transition-all ${
                  step > s.num
                    ? "bg-emerald-500 text-black shadow-[0_0_15px_rgba(16,185,129,0.4)]"
                    : step === s.num
                    ? "bg-white text-black ring-4 ring-emerald-500/20"
                    : "bg-zinc-800 text-zinc-400 border border-white/[0.05]"
                }`}
              >
                {step > s.num ? <Check className="h-4 w-4" /> : s.num}
              </div>
              <span
                className={`text-[11px] font-medium transition-colors ${
                  step === s.num ? "text-white" : "text-zinc-500"
                }`}
              >
                {s.title}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Main Step Body */}
      <main className="max-w-2xl mx-auto w-full px-6 py-10 flex-1 flex flex-col justify-center">
        {/* STEP 1: IDENTITY */}
        {step === 1 && (
          <div className="p-8 rounded-2xl bg-[#121215] border border-white/[0.08] shadow-2xl">
            <div className="mb-6">
              <span className="text-xs uppercase tracking-widest text-emerald-400 font-mono">
                Step 1 of 5
              </span>
              <h2 className="text-2xl font-semibold text-white mt-1">
                Restaurant Identity & Operating Details
              </h2>
              <p className="text-xs text-zinc-400 mt-1">
                This information grounds your Roman Urdu AI agent to answer customer inquiries accurately.
              </p>
            </div>

            <form onSubmit={handleSaveIdentity} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                  Restaurant Name
                </label>
                <input
                  type="text"
                  value={restaurantName}
                  onChange={(e) => setRestaurantName(e.target.value)}
                  required
                  className="w-full h-11 px-3.5 rounded-lg bg-[#09090b] border border-white/[0.1] text-sm text-white focus:outline-none focus:border-emerald-500/50 transition-colors"
                  placeholder="e.g. Da Pakhtun Dera"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                    Cuisine Specialty
                  </label>
                  <input
                    type="text"
                    value={cuisine}
                    onChange={(e) => setCuisine(e.target.value)}
                    required
                    className="w-full h-11 px-3.5 rounded-lg bg-[#09090b] border border-white/[0.1] text-sm text-white focus:outline-none focus:border-emerald-500/50"
                    placeholder="e.g. Shinwari Karahi & BBQ"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                    City
                  </label>
                  <input
                    type="text"
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    required
                    className="w-full h-11 px-3.5 rounded-lg bg-[#09090b] border border-white/[0.1] text-sm text-white focus:outline-none focus:border-emerald-500/50"
                    placeholder="e.g. Kohat / Islamabad"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                  Full Address
                </label>
                <input
                  type="text"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  required
                  className="w-full h-11 px-3.5 rounded-lg bg-[#09090b] border border-white/[0.1] text-sm text-white focus:outline-none focus:border-emerald-500/50"
                  placeholder="e.g. Ring Road Near Bypass, Kohat"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                    Operating Hours
                  </label>
                  <input
                    type="text"
                    value={openingHours}
                    onChange={(e) => setOpeningHours(e.target.value)}
                    required
                    className="w-full h-11 px-3.5 rounded-lg bg-[#09090b] border border-white/[0.1] text-sm text-white focus:outline-none focus:border-emerald-500/50"
                    placeholder="e.g. 12:00 PM – 01:00 AM"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                    Kitchen Staff WhatsApp (For Order Slips)
                  </label>
                  <input
                    type="text"
                    value={kitchenPhone}
                    onChange={(e) => setKitchenPhone(e.target.value)}
                    required
                    className="w-full h-11 px-3.5 rounded-lg bg-[#09090b] border border-white/[0.1] text-sm text-white font-mono focus:outline-none focus:border-emerald-500/50"
                    placeholder="e.g. 923417268523"
                  />
                </div>
              </div>

              <div className="pt-4 flex justify-end">
                <button
                  type="submit"
                  disabled={identityMutation.isPending || startMutation.isPending}
                  className="h-11 px-6 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs transition-all flex items-center gap-2 shadow-[0_0_20px_rgba(16,185,129,0.3)] disabled:opacity-50"
                >
                  {identityMutation.isPending ? "Saving..." : "Continue to Menu"}
                  <ArrowRight className="h-3.5 w-3.5" />
                </button>
              </div>
            </form>
          </div>
        )}

        {/* STEP 2: MENU SETUP */}
        {step === 2 && (
          <div className="p-8 rounded-2xl bg-[#121215] border border-white/[0.08] shadow-2xl">
            <div className="mb-6">
              <span className="text-xs uppercase tracking-widest text-emerald-400 font-mono">
                Step 2 of 5
              </span>
              <h2 className="text-2xl font-semibold text-white mt-1">
                Menu & Pricing Setup
              </h2>
              <p className="text-xs text-zinc-400 mt-1">
                Your AI agent uses this direct catalog to compute exact totals in Rs. with zero hallucinations.
              </p>
            </div>

            <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
              {menuItems.map((item, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-xl bg-[#09090b] border border-white/[0.06] flex items-center justify-between"
                >
                  <div>
                    <div className="text-sm font-medium text-white">{item.name}</div>
                    <div className="text-[11px] text-zinc-500">{item.category}</div>
                  </div>
                  <div className="text-right">
                    <span className="text-sm font-mono font-semibold text-emerald-400">
                      Rs. {item.price.toLocaleString()}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-6 pt-4 border-t border-white/[0.08] flex items-center justify-between">
              <button
                type="button"
                onClick={() => setStep(1)}
                className="text-xs text-zinc-400 hover:text-white flex items-center gap-1.5 transition-colors"
              >
                <ArrowLeft className="h-3.5 w-3.5" /> Back
              </button>

              <button
                type="button"
                onClick={handleSaveMenu}
                disabled={menuMutation.isPending}
                className="h-11 px-6 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs transition-all flex items-center gap-2 shadow-[0_0_20px_rgba(16,185,129,0.3)] disabled:opacity-50"
              >
                {menuMutation.isPending ? "Ingesting..." : "Confirm & Connect WhatsApp"}
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        )}

        {/* STEP 3: META EMBEDDED SIGNUP */}
        {step === 3 && (
          <div className="p-8 rounded-2xl bg-[#121215] border border-white/[0.08] shadow-2xl">
            <div className="mb-6">
              <span className="text-xs uppercase tracking-widest text-emerald-400 font-mono">
                Step 3 of 5
              </span>
              <h2 className="text-2xl font-semibold text-white mt-1">
                Connect WhatsApp Business
              </h2>
              <p className="text-xs text-zinc-400 mt-1">
                Link your official WhatsApp Business line in 90 seconds via Meta’s official Embedded Signup.
              </p>
            </div>

            <div className="p-6 rounded-xl bg-gradient-to-b from-[#18181d] to-[#0f0f12] border border-white/[0.08] text-center">
              <div className="h-12 w-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 mx-auto mb-4">
                <Smartphone className="h-6 w-6" />
              </div>
              <h3 className="text-base font-semibold text-white">
                Meta 1-Click Embedded Dialog
              </h3>
              <p className="text-xs text-zinc-400 max-w-sm mx-auto mt-1.5 leading-relaxed">
                Logs into Facebook, verifies your restaurant phone number via SMS OTP, and connects the official Meta Cloud API.
              </p>

              <button
                type="button"
                onClick={handleConnectWhatsApp}
                disabled={whatsappMutation.isPending}
                className="mt-6 h-12 px-8 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-sm transition-all inline-flex items-center gap-2 shadow-[0_0_30px_rgba(16,185,129,0.3)]"
              >
                <ShieldCheck className="h-4 w-4" />
                {whatsappMutation.isPending ? "Connecting to Meta..." : "Connect WhatsApp with Meta"}
              </button>
            </div>

            {/* Sandbox Toggle */}
            <div className="mt-4 pt-4 border-t border-white/[0.05]">
              <button
                type="button"
                onClick={() => setIsSandboxMode(!isSandboxMode)}
                className="text-[11px] text-zinc-500 hover:text-zinc-300 underline"
              >
                {isSandboxMode ? "Hide Sandbox Mode" : "Use Sandbox / Manual Developer Token"}
              </button>

              {isSandboxMode && (
                <div className="mt-3 p-4 rounded-xl bg-[#09090b] border border-white/[0.06] space-y-3 text-xs">
                  <div>
                    <label className="block text-zinc-400 mb-1 font-mono">Phone Number ID</label>
                    <input
                      type="text"
                      value={phoneNumberId}
                      onChange={(e) => setPhoneNumberId(e.target.value)}
                      className="w-full h-9 px-3 rounded bg-zinc-900 border border-white/10 text-white font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-zinc-400 mb-1 font-mono">Meta Access Token (Optional)</label>
                    <input
                      type="password"
                      value={accessToken}
                      onChange={(e) => setAccessToken(e.target.value)}
                      placeholder="EAA..."
                      className="w-full h-9 px-3 rounded bg-zinc-900 border border-white/10 text-white font-mono"
                    />
                  </div>
                </div>
              )}
            </div>

            <div className="mt-6 flex justify-between items-center">
              <button
                type="button"
                onClick={() => setStep(2)}
                className="text-xs text-zinc-400 hover:text-white flex items-center gap-1.5 transition-colors"
              >
                <ArrowLeft className="h-3.5 w-3.5" /> Back
              </button>
            </div>
          </div>
        )}

        {/* STEP 4: KITCHEN TEST TICKET */}
        {step === 4 && (
          <div className="p-8 rounded-2xl bg-[#121215] border border-white/[0.08] shadow-2xl">
            <div className="mb-6">
              <span className="text-xs uppercase tracking-widest text-emerald-400 font-mono">
                Step 4 of 5
              </span>
              <h2 className="text-2xl font-semibold text-white mt-1">
                Kitchen WhatsApp Slip Verification
              </h2>
              <p className="text-xs text-zinc-400 mt-1">
                Before going live, let’s fire a formatted test ticket to make sure your kitchen staff line is receiving slips.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-[#09090b] border border-white/[0.06] font-mono text-xs text-zinc-300 mb-6">
              <div className="text-amber-400 font-bold">🔔 KITCHEN TICKET #TEST-01</div>
              <div className="text-zinc-600 my-1">━━━━━━━━━━━━━━━━━━━━━━━━━━━━</div>
              <div>• 1x Shinwari Mutton Karahi (Full)</div>
              <div>• 2x Roghani Naan</div>
              <div>• 1x Peshawari Kahwa</div>
              <div className="text-zinc-600 my-1">━━━━━━━━━━━━━━━━━━━━━━━━━━━━</div>
              <div className="text-emerald-400 font-bold">Total: Rs. 2,560 (TEST COD)</div>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                  Confirm Kitchen Phone Number
                </label>
                <input
                  type="text"
                  value={kitchenPhone}
                  onChange={(e) => setKitchenPhone(e.target.value)}
                  className="w-full h-11 px-3.5 rounded-lg bg-[#09090b] border border-white/[0.1] text-sm text-white font-mono"
                />
              </div>

              <div className="flex items-center justify-between pt-2">
                <button
                  type="button"
                  onClick={() => setStep(3)}
                  className="text-xs text-zinc-400 hover:text-white flex items-center gap-1.5 transition-colors"
                >
                  <ArrowLeft className="h-3.5 w-3.5" /> Back
                </button>

                <button
                  type="button"
                  onClick={handleSendTestTicket}
                  disabled={kitchenMutation.isPending}
                  className="h-11 px-6 rounded-lg bg-amber-500 hover:bg-amber-400 text-black font-semibold text-xs transition-all flex items-center gap-2 shadow-[0_0_20px_rgba(245,158,11,0.3)]"
                >
                  <Send className="h-3.5 w-3.5" />
                  {kitchenMutation.isPending ? "Sending Slip..." : "Send Test Kitchen Slip"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* STEP 5: READY TO LAUNCH */}
        {step === 5 && (
          <div className="p-8 rounded-2xl bg-[#121215] border border-white/[0.08] shadow-2xl text-center">
            <div className="h-16 w-16 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 mx-auto mb-4 animate-bounce">
              <Sparkles className="h-8 w-8" />
            </div>

            <span className="text-xs uppercase tracking-widest text-emerald-400 font-mono">
              Ready to Serve
            </span>
            <h2 className="text-3xl font-semibold text-white mt-1">
              Your Autonomous Restaurant is Live!
            </h2>
            <p className="text-xs text-zinc-400 max-w-md mx-auto mt-2">
              Customers can now message your WhatsApp number to view dishes, place orders in Roman Urdu, and receive live delivery tracking.
            </p>

            {/* Custom Link Box */}
            <div className="mt-6 p-4 rounded-xl bg-[#09090b] border border-white/[0.08] flex items-center justify-between">
              <div className="text-left font-mono text-xs text-zinc-300 truncate mr-3">
                https://wa.me/{kitchenPhone}?text=Assalam-o-Alaikum
              </div>
              <a
                href={`https://wa.me/${kitchenPhone}?text=Assalam-o-Alaikum`}
                target="_blank"
                rel="noopener noreferrer"
                className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium flex items-center gap-1 shrink-0"
              >
                Open Chat <ExternalLink className="h-3 w-3" />
              </a>
            </div>

            <div className="mt-8 flex flex-wrap justify-center gap-4">
              <Link
                href="/kds"
                className="h-11 px-6 rounded-xl bg-white text-black font-medium text-xs hover:bg-zinc-200 transition-all flex items-center gap-2"
              >
                <Radio className="h-3.5 w-3.5 text-emerald-600 animate-pulse" />
                Launch Live Kitchen Display (KDS)
              </Link>
              <Link
                href="/"
                className="h-11 px-6 rounded-xl bg-[#18181d] text-zinc-300 font-medium text-xs hover:text-white border border-white/10 transition-all flex items-center gap-2"
              >
                Back to Home
              </Link>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-white/[0.07] py-4 px-6 text-center text-[11px] text-zinc-600">
        Multi-Tenant WhatsApp Operations Platform • Da Pakhtun Dera AI
      </footer>
    </div>
  );
}
