"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  ChefHat,
  Radio,
  Clock,
  ArrowRight,
  CheckCircle2,
  AlertCircle,
  Volume2,
  VolumeX,
  RefreshCw,
  Home,
} from "lucide-react";
import { useOrders, useUpdateOrderStatus } from "@/hooks/use-orders";
import type { LiveOrder, OrderStatus } from "@/types";

export default function KitchenDisplayPage() {
  const [activeTenantId, setActiveTenantId] = useState<string>("");
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [currentTime, setCurrentTime] = useState<string>("");

  // Keep a live clock
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setCurrentTime(
        now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
      );
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  // Set default tenant (e.g. Da Pakhtun Dera pilot)
  useEffect(() => {
    // In production this would come from tenant context or URL
    setActiveTenantId("da-pakhtun-dera");
  }, []);

  const { data: orders = [], isLoading, refetch } = useOrders(activeTenantId);
  const updateStatusMutation = useUpdateOrderStatus(activeTenantId);

  // Filter orders into active vs completed
  const activeOrders = orders.filter(
    (o) => o.status === "pending" || o.status === "confirmed" || o.status === "preparing"
  );
  const deliveringOrders = orders.filter((o) => o.status === "out_for_delivery");
  const completedOrders = orders.filter((o) => o.status === "delivered");

  // Status progression map
  const getNextStatus = (current: OrderStatus): OrderStatus | null => {
    if (current === "pending" || current === "confirmed") return "preparing";
    if (current === "preparing") return "out_for_delivery";
    if (current === "out_for_delivery") return "delivered";
    return null;
  };

  const getActionLabel = (current: OrderStatus): string => {
    if (current === "pending" || current === "confirmed") return "Start Cooking";
    if (current === "preparing") return "Mark Ready (Pack)";
    if (current === "out_for_delivery") return "Mark Delivered";
    return "Completed";
  };

  const handleStatusChange = (orderId: string, currentStatus: OrderStatus) => {
    const next = getNextStatus(currentStatus);
    if (next) {
      updateStatusMutation.mutate({ orderId, status: next });
    }
  };

  // Compute elapsed minutes
  const getElapsed = (isoDate?: string) => {
    if (!isoDate) return 0;
    const diffMs = Date.now() - new Date(isoDate).getTime();
    return Math.floor(diffMs / 60000);
  };

  return (
    <div className="min-h-screen bg-[#09090b] text-[#f4f4f5] flex flex-col selection:bg-emerald-500/20 selection:text-emerald-300">
      {/* Top KDS Bar */}
      <header className="border-b border-white/[0.08] bg-[#0c0c0e] px-6 py-3.5 sticky top-0 z-20">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/" className="h-9 w-9 rounded-lg bg-white/[0.05] border border-white/[0.08] flex items-center justify-center text-zinc-400 hover:text-white transition-colors">
              <Home className="h-4 w-4" />
            </Link>

            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 font-bold">
                <ChefHat className="h-5 w-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-base font-semibold tracking-tight text-white">
                    Kitchen Display System (KDS)
                  </h1>
                  <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    LIVE
                  </span>
                </div>
                <div className="text-[11px] text-zinc-400">
                  Da Pakhtun Dera • Dual-Channel Kitchen Station
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {/* Live Clock */}
            <div className="font-mono text-sm text-zinc-300 bg-white/[0.03] border border-white/[0.06] px-3 py-1.5 rounded-lg">
              {currentTime || "00:00:00"}
            </div>

            {/* Sound Toggle */}
            <button
              onClick={() => setSoundEnabled(!soundEnabled)}
              className={`h-9 w-9 rounded-lg border flex items-center justify-center transition-colors ${
                soundEnabled
                  ? "bg-white/[0.05] border-white/[0.1] text-emerald-400"
                  : "bg-red-500/10 border-red-500/30 text-red-400"
              }`}
            >
              {soundEnabled ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
            </button>

            {/* Refresh */}
            <button
              onClick={() => refetch()}
              className="h-9 px-3 rounded-lg bg-white/[0.05] hover:bg-white/[0.08] border border-white/[0.1] text-xs font-medium text-zinc-300 flex items-center gap-1.5 transition-colors"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>
        </div>
      </header>

      {/* Main Ticket Grid */}
      <main className="flex-1 p-6 max-w-[1600px] w-full mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold text-white">Active Kitchen Tickets</h2>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
              {activeOrders.length} to cook
            </span>
          </div>
        </div>

        {activeOrders.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-white/[0.1] p-16 text-center">
            <ChefHat className="h-12 w-12 text-zinc-600 mx-auto mb-3" />
            <h3 className="text-base font-medium text-zinc-300">All caught up, Chef!</h3>
            <p className="text-xs text-zinc-500 mt-1 max-w-sm mx-auto">
              New customer orders placed on WhatsApp will appear here automatically with instant audio chime.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {activeOrders.map((order) => {
              const elapsed = getElapsed(order.created_at);
              const isUrgent = elapsed >= 20;

              return (
                <div
                  key={order.id}
                  className={`rounded-2xl bg-[#121215] border p-5 flex flex-col justify-between shadow-xl transition-all ${
                    isUrgent
                      ? "border-amber-500/50 shadow-[0_0_20px_rgba(245,158,11,0.15)]"
                      : "border-white/[0.08]"
                  }`}
                >
                  <div>
                    {/* Ticket Header */}
                    <div className="flex items-center justify-between border-b border-white/[0.08] pb-3 mb-3">
                      <div>
                        <span className="font-mono text-base font-bold text-white tracking-tight">
                          #{order.order_number}
                        </span>
                        <div className="text-[11px] font-mono text-zinc-400 capitalize">
                          {order.delivery_type}
                        </div>
                      </div>

                      <div
                        className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-mono font-medium ${
                          isUrgent
                            ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                            : "bg-white/[0.05] text-zinc-300 border border-white/[0.08]"
                        }`}
                      >
                        <Clock className="h-3 w-3" />
                        {elapsed}m
                      </div>
                    </div>

                    {/* Address / Customer */}
                    {order.delivery_address && (
                      <div className="text-xs text-zinc-400 mb-3 pb-3 border-b border-white/[0.05] truncate">
                        📍 {order.delivery_address}
                      </div>
                    )}

                    {/* Order Items to Cook */}
                    <div className="space-y-2.5 my-2">
                      {order.items && order.items.length > 0 ? (
                        order.items.map((item, idx) => (
                          <div key={idx} className="text-xs">
                            <div className="flex items-baseline justify-between font-semibold text-white">
                              <span>
                                <span className="text-amber-400 font-mono mr-1.5">
                                  {item.quantity}x
                                </span>
                                {item.name}
                              </span>
                            </div>
                            {item.notes && (
                              <div className="text-[11px] text-zinc-400 pl-4 italic mt-0.5">
                                ↳ {item.notes}
                              </div>
                            )}
                          </div>
                        ))
                      ) : (
                        <div className="text-xs text-zinc-400">
                          • 1x Shinwari Mutton Karahi (Full)
                          <br />• 4x Roghani Naan
                        </div>
                      )}
                    </div>

                    {order.customer_notes && (
                      <div className="mt-3 p-2 rounded bg-black/40 border border-white/[0.05] text-[11px] text-zinc-400 italic">
                        Note: {order.customer_notes}
                      </div>
                    )}
                  </div>

                  {/* Footer & Action Button */}
                  <div className="mt-5 pt-3 border-t border-white/[0.08] flex items-center justify-between gap-3">
                    <div className="font-mono font-bold text-xs text-emerald-400">
                      Rs. {order.total_amount.toLocaleString()}
                    </div>

                    <button
                      onClick={() => handleStatusChange(order.id, order.status)}
                      disabled={updateStatusMutation.isPending}
                      className="h-10 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs transition-all flex items-center gap-1.5 shadow-[0_0_15px_rgba(16,185,129,0.25)] active:scale-95 disabled:opacity-50"
                    >
                      {getActionLabel(order.status)}
                      <ArrowRight className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Recently Delivered Bar */}
        {deliveringOrders.length > 0 && (
          <div className="mt-12">
            <h3 className="text-sm font-semibold text-zinc-400 mb-4">
              Out for Delivery ({deliveringOrders.length})
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {deliveringOrders.map((ord) => (
                <div
                  key={ord.id}
                  className="p-4 rounded-xl bg-[#0e0e11] border border-white/[0.06] flex items-center justify-between text-xs"
                >
                  <div>
                    <span className="font-mono font-bold text-white">#{ord.order_number}</span>
                    <div className="text-[11px] text-zinc-500">{ord.delivery_address || "Delivery"}</div>
                  </div>
                  <button
                    onClick={() => handleStatusChange(ord.id, ord.status)}
                    className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium border border-white/[0.08]"
                  >
                    Mark Delivered
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
