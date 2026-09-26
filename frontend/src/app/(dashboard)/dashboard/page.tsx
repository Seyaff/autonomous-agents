"use client"

import React, { useEffect, useState, useRef } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  DollarSign,
  ShoppingBag,
  Clock,
  CheckCircle,
  XCircle,
  Sparkles,
  RefreshCw,
  Send,
  MessageSquare
} from "lucide-react"
import API from "@/lib/axios-client"

interface Order {
  _id: string
  order_id: string
  tenant_id: string
  customer_phone: string
  customer_name?: string
  delivery_address: string
  items: Array<{ name: string; quantity: number; price: number }>
  total_amount: number
  status: string
  payment_method: string
  created_at: string
}

interface StatsSummary {
  total_orders: number
  total_revenue: number
  pending_orders: number
  completed_orders: number
  cancelled_orders: number
}

interface WeeklyReport {
  _id?: string
  business_name: string
  summary: string
  created_at: string
  delivered_via_whatsapp: boolean
}

export default function DashboardPage() {
  const [orders, setOrders] = useState<Order[]>([])
  const [stats, setStats] = useState<StatsSummary>({
    total_orders: 0,
    total_revenue: 0,
    pending_orders: 0,
    completed_orders: 0,
    cancelled_orders: 0,
  })
  const [weeklyReport, setWeeklyReport] = useState<WeeklyReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [reportLoading, setReportLoading] = useState(false)
  const [tenant, setTenant] = useState<any>(null)
  const [wsConnected, setWsConnected] = useState(false)
  const socketRef = useRef<WebSocket | null>(null)

  const fetchData = async () => {
    try {
      // 1. Fetch current tenant
      const tenantRes = await API.get("/tenant/current")
      const currentTenant = tenantRes.data
      setTenant(currentTenant)

      // 2. Fetch stats summary
      const statsRes = await API.get("/orders/stats/summary")
      setStats(statsRes.data)

      // 3. Fetch latest orders
      const ordersRes = await API.get("/orders?limit=25")
      setOrders(ordersRes.data.orders || [])

      // 4. Fetch latest weekly report
      const repRes = await API.get("/analytics/weekly-reports")
      if (repRes.data.reports && repRes.data.reports.length > 0) {
        setWeeklyReport(repRes.data.reports[0])
      }
    } catch (err: any) {
      console.error("Dashboard fetch error:", err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  // Setup WebSocket connection for real-time order updates
  useEffect(() => {
    if (!tenant?.tenant_id) return

    const wsUrl = `ws://localhost:8000/ws/tenants/${tenant.tenant_id}/orders`
    const ws = new WebSocket(wsUrl)
    socketRef.current = ws

    ws.onopen = () => {
      console.log("WebSocket connected for tenant:", tenant.tenant_id)
      setWsConnected(true)
    }

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)
        console.log("Realtime event received:", payload)

        if (payload.event === "order.created") {
          const newOrder = payload.data
          setOrders((prev) => [newOrder, ...prev.filter((o) => o.order_id !== newOrder.order_id)])
          setStats((prev) => ({
            ...prev,
            total_orders: prev.total_orders + 1,
            pending_orders: prev.pending_orders + 1,
            total_revenue: prev.total_revenue + (newOrder.total_amount || 0),
          }))
        } else if (payload.event === "order.updated" || payload.event === "order.cancelled") {
          const updated = payload.data
          setOrders((prev) =>
            prev.map((o) => (o.order_id === updated.order_id ? { ...o, ...updated } : o))
          )
        } else if (payload.event === "report.weekly_generated") {
          setWeeklyReport(payload.data)
        }
      } catch (e) {
        console.error("WS message parse error:", e)
      }
    }

    ws.onclose = () => {
      setWsConnected(false)
    }

    return () => {
      ws.close()
    }
  }, [tenant?.tenant_id])

  const handleUpdateOrderStatus = async (orderId: string, newStatus: string) => {
    try {
      await API.patch(`/orders/${orderId}`, { status: newStatus })
      setOrders((prev) =>
        prev.map((o) => (o.order_id === orderId ? { ...o, status: newStatus } : o))
      )
    } catch (e) {
      console.error("Failed to update status:", e)
    }
  }

  const handleGenerateWeeklyReport = async () => {
    setReportLoading(true)
    try {
      const res = await API.post("/analytics/weekly/generate")
      if (res.data.report) {
        setWeeklyReport(res.data.report)
      }
    } catch (e) {
      console.error("Could not trigger weekly report:", e)
    } finally {
      setReportLoading(false)
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case "pending":
        return <Badge variant="outline" className="bg-amber-100 text-amber-800 border-amber-300">Pending</Badge>
      case "accepted":
        return <Badge variant="outline" className="bg-blue-100 text-blue-800 border-blue-300">Accepted</Badge>
      case "preparing":
        return <Badge variant="outline" className="bg-purple-100 text-purple-800 border-purple-300">Preparing</Badge>
      case "delivered":
        return <Badge variant="outline" className="bg-green-100 text-green-800 border-green-300">Delivered</Badge>
      case "cancelled":
        return <Badge variant="outline" className="bg-red-100 text-red-800 border-red-300">Cancelled</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  return (
    <div className="space-y-6">
      {/* Top Banner & Live Status */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b pb-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            {tenant?.business_name || "Restaurant"} Dashboard
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Real-time autopilot management for incoming WhatsApp orders, customer conversations, and weekly intelligence.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 rounded-full border bg-background px-3 py-1.5 text-xs font-medium shadow-xs">
            <span className={`size-2.5 rounded-full ${wsConnected ? "bg-green-500 animate-pulse" : "bg-amber-500"}`} />
            {wsConnected ? "AI Agent Live on WhatsApp" : "Connecting Agent Stream..."}
          </div>
          <Button variant="outline" size="sm" onClick={fetchData}>
            <RefreshCw className="size-3.5 mr-1" />
            Refresh
          </Button>
        </div>
      </div>

      {/* METRIC CARDS */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Revenue</CardTitle>
            <DollarSign className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {tenant?.currency || "USD"} {stats.total_revenue.toFixed(2)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">From processed WhatsApp orders</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Orders</CardTitle>
            <ShoppingBag className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total_orders}</div>
            <p className="text-xs text-muted-foreground mt-1">Lifetime customer orders</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Active / Pending</CardTitle>
            <Clock className="size-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-600">{stats.pending_orders}</div>
            <p className="text-xs text-muted-foreground mt-1">Orders requiring action</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Delivered & Completed</CardTitle>
            <CheckCircle className="size-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{stats.completed_orders}</div>
            <p className="text-xs text-muted-foreground mt-1">Fulfilled successfully</p>
          </CardContent>
        </Card>
      </div>

      {/* LIVE ORDERS SECTION */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Live WhatsApp Order Stream</CardTitle>
            <CardDescription>
              Orders placed by customers through your autonomous AI WhatsApp assistant update here in real-time.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="py-8 text-center text-muted-foreground">Loading orders...</div>
          ) : orders.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">
              <MessageSquare className="size-10 mx-auto text-muted-foreground/50 mb-3" />
              <p className="font-medium text-foreground">No orders received yet.</p>
              <p className="text-xs text-muted-foreground mt-1">
                Send a WhatsApp message like "I want 2 Pepperoni Pizzas" to your connected number to see it appear here live!
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="text-xs uppercase bg-muted/50 border-b">
                  <tr>
                    <th className="px-4 py-3">Order ID</th>
                    <th className="px-4 py-3">Customer</th>
                    <th className="px-4 py-3">Items</th>
                    <th className="px-4 py-3">Delivery Address</th>
                    <th className="px-4 py-3">Amount</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {orders.map((order) => (
                    <tr key={order.order_id} className="hover:bg-muted/20">
                      <td className="px-4 py-3 font-semibold font-mono">{order.order_id}</td>
                      <td className="px-4 py-3 text-xs">
                        <div className="font-medium">{order.customer_name || "Customer"}</div>
                        <div className="text-muted-foreground">{order.customer_phone}</div>
                      </td>
                      <td className="px-4 py-3 text-xs max-w-xs">
                        {order.items?.map((item, idx) => (
                          <span key={idx} className="inline-block mr-2 font-medium">
                            {item.quantity}x {item.name}
                          </span>
                        ))}
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground max-w-xs truncate">
                        {order.delivery_address || "Pickup"}
                      </td>
                      <td className="px-4 py-3 font-semibold">
                        {tenant?.currency || "$"}{Number(order.total_amount || 0).toFixed(2)}
                      </td>
                      <td className="px-4 py-3">{getStatusBadge(order.status)}</td>
                      <td className="px-4 py-3 text-right space-x-1">
                        {order.status === "pending" && (
                          <Button
                            size="xs"
                            variant="default"
                            onClick={() => handleUpdateOrderStatus(order.order_id, "accepted")}
                          >
                            Accept
                          </Button>
                        )}
                        {order.status === "accepted" && (
                          <Button
                            size="xs"
                            variant="secondary"
                            onClick={() => handleUpdateOrderStatus(order.order_id, "preparing")}
                          >
                            In Kitchen
                          </Button>
                        )}
                        {order.status === "preparing" && (
                          <Button
                            size="xs"
                            className="bg-green-600 hover:bg-green-700 text-white"
                            onClick={() => handleUpdateOrderStatus(order.order_id, "delivered")}
                          >
                            Mark Delivered
                          </Button>
                        )}
                        {["pending", "accepted"].includes(order.status) && (
                          <Button
                            size="xs"
                            variant="ghost"
                            className="text-destructive hover:bg-destructive/10"
                            onClick={() => handleUpdateOrderStatus(order.order_id, "cancelled")}
                          >
                            Decline
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 7-DAY AUTOPILOT BUSINESS REPORT CARD */}
      <Card className="border-primary/20 bg-primary/5">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Sparkles className="size-5 text-primary" />
              <CardTitle>7-Day Autopilot Business Intelligence</CardTitle>
            </div>
            <CardDescription className="mt-1">
              Autonomous weekly executive summary generated every 7 days and sent directly to your WhatsApp.
            </CardDescription>
          </div>
          <Button
            size="sm"
            onClick={handleGenerateWeeklyReport}
            disabled={reportLoading}
          >
            {reportLoading ? "Analyzing..." : "Generate New Report"}
          </Button>
        </CardHeader>
        <CardContent>
          {weeklyReport ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between text-xs text-muted-foreground border-b pb-2">
                <span>Report Date: {new Date(weeklyReport.created_at).toLocaleDateString()}</span>
                {weeklyReport.delivered_via_whatsapp && (
                  <span className="text-green-600 font-medium flex items-center gap-1">
                    <CheckCircle className="size-3.5" /> Sent to Owner's WhatsApp
                  </span>
                )}
              </div>
              <div className="prose prose-sm max-w-none text-foreground whitespace-pre-wrap font-sans text-sm leading-relaxed">
                {weeklyReport.summary}
              </div>
            </div>
          ) : (
            <div className="py-6 text-center text-muted-foreground text-sm">
              No weekly report generated yet. Click "Generate New Report" to produce your first 7-day executive briefing!
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}