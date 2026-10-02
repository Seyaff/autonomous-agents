"use client"

import * as React from "react"
import {
  columnFilteringFeature,
  columnVisibilityFeature,
  createColumnHelper,
  createFilteredRowModel,
  createPaginatedRowModel,
  createSortedRowModel,
  FlexRender,
  rowPaginationFeature,
  rowSelectionFeature,
  rowSortingFeature,
  tableFeatures,
  useTable,
  type ColumnFiltersState,
  type ColumnVisibilityState,
  type PaginationState,
  type SortingState,
} from "@tanstack/react-table"
import {
  ChevronDownIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronsLeftIcon,
  ChevronsRightIcon,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Skeleton } from "@/components/ui/skeleton"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { StatusChip } from "@/components/console/status-chip"
import { Ticket } from "@/components/console/ticket"
import { cn } from "@/lib/utils"
import { formatMoney } from "@/lib/currency"
import { ORDER_STATUS_DISPLAY, type OrderStatus } from "@/lib/status"
import type { RailOrder } from "@/hooks/console/use-rail"

const STATUS_OPTIONS: OrderStatus[] = [
  "pending",
  "accepted",
  "preparing",
  "out_for_delivery",
  "delivered",
  "cancelled",
]

const features = tableFeatures({
  columnFilteringFeature,
  columnVisibilityFeature,
  rowPaginationFeature,
  rowSelectionFeature,
  rowSortingFeature,
  filteredRowModel: createFilteredRowModel(),
  paginatedRowModel: createPaginatedRowModel(),
  sortedRowModel: createSortedRowModel(),
})

const columnHelper = createColumnHelper<typeof features, RailOrder>()

export function OrdersLedger({
  orders,
  currency,
  isLoading,
  onAdvance,
}: {
  orders: RailOrder[]
  currency: string
  isLoading: boolean
  onAdvance: (order: RailOrder, next: OrderStatus) => void
}) {
  const [statusFilter, setStatusFilter] = React.useState<OrderStatus | "all">("all")
  const [selected, setSelected] = React.useState<RailOrder | null>(null)
  const [rowSelection, setRowSelection] = React.useState({})
  const [columnVisibility, setColumnVisibility] = React.useState<ColumnVisibilityState>({})
  const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>([])
  const [sorting, setSorting] = React.useState<SortingState>([])
  const [pagination, setPagination] = React.useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  })

  const filtered = React.useMemo(
    () => (statusFilter === "all" ? orders : orders.filter((o) => o.status === statusFilter)),
    [orders, statusFilter]
  )

  // Keep the open sheet in sync with the underlying order (e.g. after
  // advancing its status from inside the sheet).
  const selectedLive = selected ? filtered.find((o) => o.order_id === selected.order_id) ?? selected : null

  const columns = React.useMemo(
    () =>
      columnHelper.columns([
        columnHelper.accessor("order_id", {
          header: () => <span className="block w-full text-right">Order ID</span>,
          cell: ({ row }) => (
            <span className="block text-right font-mono text-sm font-medium">
              {row.getValue("order_id")}
            </span>
          ),
        }),
        columnHelper.display({
          id: "customer",
          header: "Customer",
          cell: ({ row }) => (
            <div className="flex flex-col">
              <span className="text-sm font-medium">{row.original.customer_name || "Unknown"}</span>
              <span className="text-xs text-muted-foreground">{row.original.customer_phone}</span>
            </div>
          ),
        }),
        columnHelper.display({
          id: "items",
          header: "Items",
          cell: ({ row }) => {
            const summary = row.original.items.map((i) => `${i.quantity}x ${i.name}`).join(", ")
            return (
              <span className="line-clamp-1 max-w-60 text-sm text-muted-foreground">
                {summary || "—"}
              </span>
            )
          },
        }),
        columnHelper.accessor("total_amount", {
          header: () => <span className="block w-full text-right">Total</span>,
          cell: ({ row }) => (
            <span className="block text-right font-mono text-sm font-medium tabular-nums">
              {formatMoney(row.getValue("total_amount"), currency)}
            </span>
          ),
        }),
        columnHelper.accessor("status", {
          header: "Status",
          cell: ({ row }) => {
            const status = row.getValue("status") as OrderStatus
            const { label, tone } = ORDER_STATUS_DISPLAY[status]
            return <StatusChip tone={tone} label={label} />
          },
        }),
        columnHelper.accessor("created_at", {
          header: () => <span className="block w-full text-right">Placed</span>,
          cell: ({ row }) => (
            <span className="block text-right font-mono text-xs text-muted-foreground">
              {new Date(row.getValue("created_at")).toLocaleString([], {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          ),
        }),
      ]),
    [currency]
  )

  const table = useTable({
    features,
    data: filtered,
    columns,
    state: { sorting, columnVisibility, rowSelection, columnFilters, pagination },
    getRowId: (row) => row.order_id,
    enableRowSelection: true,
    onRowSelectionChange: setRowSelection,
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onColumnVisibilityChange: setColumnVisibility,
    onPaginationChange: setPagination,
  })

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* Filters sit above the table as chips, not a sidebar/select. */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            type="button"
            onClick={() => setStatusFilter("all")}
            className={cn(
              "rounded-[5px] border px-2 py-1 font-mono text-[11px] tracking-wide transition-colors",
              statusFilter === "all"
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            All · {orders.length}
          </button>
          {STATUS_OPTIONS.map((s) => {
            const { label, tone } = ORDER_STATUS_DISPLAY[s]
            const count = orders.filter((o) => o.status === s).length
            return (
              <button
                key={s}
                type="button"
                onClick={() => setStatusFilter(s)}
                className={cn(
                  "rounded-[5px] transition-opacity",
                  statusFilter === s ? "opacity-100" : "opacity-45 hover:opacity-80"
                )}
              >
                <StatusChip tone={tone} label={`${label} · ${count}`} />
              </button>
            )
          })}
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger className="inline-flex h-8 items-center gap-2 rounded-md border border-border bg-background px-3 text-sm font-medium hover:bg-accent">
            Columns
            <ChevronDownIcon className="size-4" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            {table
              .getAllColumns()
              .filter((column) => typeof column.accessorFn !== "undefined" && column.getCanHide())
              .map((column) => (
                <DropdownMenuCheckboxItem
                  key={column.id}
                  className="capitalize"
                  checked={column.getIsVisible()}
                  onCheckedChange={(value) => column.toggleVisibility(!!value)}
                >
                  {column.id}
                </DropdownMenuCheckboxItem>
              ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div className="overflow-hidden rounded-lg border border-border">
        <Table>
          <TableHeader className="bg-muted/50">
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead
                    key={header.id}
                    colSpan={header.colSpan}
                    className="font-mono text-[11px] tracking-[.08em] text-muted-foreground uppercase"
                  >
                    {header.isPlaceholder ? null : <FlexRender header={header} />}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i} className="h-11">
                  <TableCell colSpan={columns.length} className="py-0">
                    <Skeleton className="h-4 w-full" />
                  </TableCell>
                </TableRow>
              ))
            ) : table.getRowModel().rows.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() && "selected"}
                  className="h-11 cursor-pointer transition-colors hover:bg-muted/50"
                  onClick={() => setSelected(row.original)}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id} className="py-0">
                      <FlexRender cell={cell} />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center font-mono text-xs text-muted-foreground"
                >
                  No orders found.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between px-1">
        <div className="hidden text-sm text-muted-foreground lg:flex">
          {table.getFilteredSelectedRowModel().rows.length} of{" "}
          {table.getFilteredRowModel().rows.length} row(s) selected.
        </div>
        <div className="flex w-full items-center gap-6 lg:w-fit">
          <div className="hidden items-center gap-2 lg:flex">
            <Label htmlFor="rows-per-page" className="text-sm font-medium">
              Rows per page
            </Label>
            <Select value={`${pagination.pageSize}`} onValueChange={(value) => table.setPageSize(Number(value))}>
              <SelectTrigger size="sm" className="w-20" id="rows-per-page">
                <SelectValue />
              </SelectTrigger>
              <SelectContent side="top">
                {[10, 20, 30, 40, 50].map((pageSize) => (
                  <SelectItem key={pageSize} value={`${pageSize}`}>
                    {pageSize}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex w-fit items-center justify-center text-sm font-medium">
            Page {pagination.pageIndex + 1} of {Math.max(table.getPageCount(), 1)}
          </div>
          <div className="ml-auto flex items-center gap-2 lg:ml-0">
            <Button
              variant="outline"
              className="hidden size-8 p-0 lg:flex"
              onClick={() => table.setPageIndex(0)}
              disabled={!table.getCanPreviousPage()}
            >
              <span className="sr-only">Go to first page</span>
              <ChevronsLeftIcon className="size-4" />
            </Button>
            <Button
              variant="outline"
              className="size-8"
              size="icon"
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
            >
              <span className="sr-only">Go to previous page</span>
              <ChevronLeftIcon className="size-4" />
            </Button>
            <Button
              variant="outline"
              className="size-8"
              size="icon"
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
            >
              <span className="sr-only">Go to next page</span>
              <ChevronRightIcon className="size-4" />
            </Button>
            <Button
              variant="outline"
              className="hidden size-8 lg:flex"
              size="icon"
              onClick={() => table.setPageIndex(table.getPageCount() - 1)}
              disabled={!table.getCanNextPage()}
            >
              <span className="sr-only">Go to last page</span>
              <ChevronsRightIcon className="size-4" />
            </Button>
          </div>
        </div>
      </div>

      <Sheet open={!!selected} onOpenChange={(open) => !open && setSelected(null)}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle className="font-mono">{selected?.order_id}</SheetTitle>
          </SheetHeader>
          {selectedLive && (
            <div className="px-4 pb-4">
              <Ticket
                order={selectedLive}
                currency={currency}
                onAdvance={(next) => onAdvance(selectedLive, next)}
              />
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  )
}
