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
  ClockIcon,
  MoreVerticalIcon,
} from "lucide-react"
import { z } from "zod"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
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
import { cn } from "@/lib/utils"

export const orderSchema = z.object({
  id: z.number(),
  orderId: z.string(),
  item: z.string(),
  quantity: z.number(),
  price: z.number(),
  state: z.enum([
    "pending",
    "confirmed",
    "in_kitchen",
    "ready",
    "delivered",
    "cancelled",
  ]),
})

export type Order = z.infer<typeof orderSchema>

const stateConfig: Record<
  Order["state"],
  { label: string; className: string }
> = {
  pending: {
    label: "Pending",
    className: "bg-yellow-100 text-yellow-800 border-yellow-200",
  },
  confirmed: {
    label: "Confirmed",
    className: "bg-blue-100 text-blue-800 border-blue-200",
  },
  in_kitchen: {
    label: "In Kitchen",
    className: "bg-orange-100 text-orange-800 border-orange-200",
  },
  ready: {
    label: "Ready",
    className: "bg-purple-100 text-purple-800 border-purple-200",
  },
  delivered: {
    label: "Delivered",
    className: "bg-green-100 text-green-800 border-green-200",
  },
  cancelled: {
    label: "Cancelled",
    className: "bg-red-100 text-red-800 border-red-200",
  },
}

const dummyOrders: Order[] = [
  { id: 1, orderId: "ORD-2024-001", item: "Chicken Biryani", quantity: 2, price: 28.5, state: "in_kitchen" },
  { id: 2, orderId: "ORD-2024-002", item: "Beef Karahi", quantity: 1, price: 19.0, state: "pending" },
  { id: 3, orderId: "ORD-2024-003", item: "Mutton Pulao", quantity: 3, price: 42.75, state: "delivered" },
  { id: 4, orderId: "ORD-2024-004", item: "Chicken Tikka", quantity: 4, price: 36.0, state: "ready" },
  { id: 5, orderId: "ORD-2024-005", item: "Nihari", quantity: 2, price: 24.5, state: "confirmed" },
  { id: 6, orderId: "ORD-2024-006", item: "Haleem", quantity: 1, price: 12.0, state: "delivered" },
  { id: 7, orderId: "ORD-2024-007", item: "Seekh Kebab", quantity: 6, price: 33.0, state: "in_kitchen" },
  { id: 8, orderId: "ORD-2024-008", item: "Butter Chicken", quantity: 2, price: 26.0, state: "pending" },
  { id: 9, orderId: "ORD-2024-009", item: "Palak Paneer", quantity: 1, price: 14.5, state: "cancelled" },
  { id: 10, orderId: "ORD-2024-010", item: "Garlic Naan", quantity: 8, price: 16.0, state: "delivered" },
  { id: 11, orderId: "ORD-2024-011", item: "Mango Lassi", quantity: 3, price: 10.5, state: "ready" },
  { id: 12, orderId: "ORD-2024-012", item: "Chicken Handi", quantity: 2, price: 31.0, state: "confirmed" },
  { id: 13, orderId: "ORD-2024-013", item: "Aloo Keema", quantity: 1, price: 17.75, state: "in_kitchen" },
  { id: 14, orderId: "ORD-2024-014", item: "Daal Makhani", quantity: 2, price: 18.0, state: "delivered" },
  { id: 15, orderId: "ORD-2024-015", item: "Chicken Shawarma", quantity: 3, price: 22.5, state: "pending" },
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

const columnHelper = createColumnHelper<typeof features, Order>()

export function OrdersTable() {
  const [data] = React.useState(() => dummyOrders)
  const [rowSelection, setRowSelection] = React.useState({})
  const [columnVisibility, setColumnVisibility] =
    React.useState<ColumnVisibilityState>({})
  const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>(
    []
  )
  const [sorting, setSorting] = React.useState<SortingState>([])
  const [pagination, setPagination] = React.useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  })

  // Build columns inside the component so "Sr No" can read pagination
  const columns = React.useMemo(
    () =>
      columnHelper.columns([
        columnHelper.display({
          id: "srNo",
          header: "Sr No",
          cell: ({ row }) => {
            const index =
              pagination.pageIndex * pagination.pageSize + row.index + 1
            return (
              <span className="text-sm tabular-nums text-muted-foreground">
                {index}
              </span>
            )
          },
          enableSorting: false,
          enableHiding: false,
        }),
        columnHelper.accessor("orderId", {
          header: "Order ID",
          cell: ({ row }) => (
            <span className="font-mono text-sm font-medium">
              {row.getValue("orderId")}
            </span>
          ),
        }),
        columnHelper.accessor("item", {
          header: "Item",
          cell: ({ row }) => (
            <span className="text-sm font-medium">{row.getValue("item")}</span>
          ),
        }),
        columnHelper.accessor("quantity", {
          header: "Quantity",
          cell: ({ row }) => (
            <span className="text-sm tabular-nums">
              {row.getValue("quantity")}
            </span>
          ),
        }),
        columnHelper.accessor("price", {
          header: () => (
            <span className="block w-full text-right">Price</span>
          ),
          cell: ({ row }) => {
            const price = row.getValue("price") as number
            return (
              <span className="block text-right font-medium tabular-nums">
                ${price.toFixed(2)}
              </span>
            )
          },
        }),
        columnHelper.accessor("state", {
          header: "State",
          cell: ({ row }) => {
            const state = row.getValue("state") as Order["state"]
            const config = stateConfig[state]
            return (
              <Badge
                variant="outline"
                className={cn(
                  "gap-1 px-2 py-0.5 text-xs font-medium",
                  config.className
                )}
              >
                {state === "in_kitchen" && <ClockIcon className="size-3" />}
                {config.label}
              </Badge>
            )
          },
        }),
        columnHelper.display({
          id: "actions",
          cell: () => (
            <DropdownMenu>
              <DropdownMenuTrigger className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted data-[state=open]:bg-muted">
                <MoreVerticalIcon className="size-4" />
                <span className="sr-only">Open menu</span>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-40">
                <DropdownMenuItem>View details</DropdownMenuItem>
                <DropdownMenuItem>Update status</DropdownMenuItem>
                <DropdownMenuItem>Print receipt</DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem variant="destructive">
                  Cancel order
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ),
        }),
      ]),
    [pagination.pageIndex, pagination.pageSize]
  )

  const table = useTable({
    features,
    data,
    columns,
    state: {
      sorting,
      columnVisibility,
      rowSelection,
      columnFilters,
      pagination,
    },
    getRowId: (row) => row.id.toString(),
    enableRowSelection: true,
    onRowSelectionChange: setRowSelection,
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onColumnVisibilityChange: setColumnVisibility,
    onPaginationChange: setPagination,
  })

  return (
    <div className="flex flex-col gap-4">
      {/* Table toolbar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">
            Recent Orders
          </h2>
          <p className="text-sm text-muted-foreground">
            A list of orders placed in your restaurant today.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select
            value={
              (columnFilters.find((f) => f.id === "state")?.value as string) ||
              "all"
            }
            onValueChange={(value) => {
              if (value === "all") {
                setColumnFilters((prev) =>
                  prev.filter((f) => f.id !== "state")
                )
              } else {
                setColumnFilters((prev) => [
                  ...prev.filter((f) => f.id !== "state"),
                  { id: "state", value },
                ])
              }
            }}
          >
            <SelectTrigger className="w-40" size="sm">
              <SelectValue placeholder="All states" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All states</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="confirmed">Confirmed</SelectItem>
              <SelectItem value="in_kitchen">In Kitchen</SelectItem>
              <SelectItem value="ready">Ready</SelectItem>
              <SelectItem value="delivered">Delivered</SelectItem>
              <SelectItem value="cancelled">Cancelled</SelectItem>
            </SelectContent>
          </Select>
          <DropdownMenu>
            <DropdownMenuTrigger className="inline-flex h-8 items-center gap-2 rounded-md border bg-background px-3 text-sm font-medium hover:bg-accent">
              Columns
              <ChevronDownIcon className="size-4" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              {table
                .getAllColumns()
                .filter(
                  (column) =>
                    typeof column.accessorFn !== "undefined" &&
                    column.getCanHide()
                )
                .map((column) => (
                  <DropdownMenuCheckboxItem
                    key={column.id}
                    className="capitalize"
                    checked={column.getIsVisible()}
                    onCheckedChange={(value) =>
                      column.toggleVisibility(!!value)
                    }
                  >
                    {column.id}
                  </DropdownMenuCheckboxItem>
                ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-lg border">
        <Table>
          <TableHeader className="bg-muted/50">
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead
                    key={header.id}
                    colSpan={header.colSpan}
                    className="text-xs font-semibold tracking-wider text-muted-foreground uppercase"
                  >
                    {header.isPlaceholder ? null : (
                      <FlexRender header={header} />
                    )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() && "selected"}
                  className="transition-colors hover:bg-muted/50"
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id} className="py-3">
                      <FlexRender cell={cell} />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center text-muted-foreground"
                >
                  No orders found.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
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
            <Select
              value={`${pagination.pageSize}`}
              onValueChange={(value) => table.setPageSize(Number(value))}
            >
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
            Page {pagination.pageIndex + 1} of {table.getPageCount()}
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
    </div>
  )
}