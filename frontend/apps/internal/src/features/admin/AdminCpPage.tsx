import {
  AlertCircle,
  Edit3,
  ExternalLink,
  Gauge,
  Loader2,
  Lock,
  LogOut,
  RefreshCw,
  Search,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Trash2,
  UserPlus,
} from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import type {
  AdminUser,
  CreateUserPayload,
  InitAdminPayload,
  UpdateUserPayload,
  UserRole,
} from '@pricepolicy/api-client/contracts'
import {
  useAdminSetup,
  useAdminSetupStatus,
  useAdminUsers,
  useCreateUser,
  useDeleteUser,
  useUpdateUser,
} from '@pricepolicy/api-client/hooks'
import { Badge } from '@pricepolicy/ui/components/ui/badge'
import { Button } from '@pricepolicy/ui/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@pricepolicy/ui/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@pricepolicy/ui/components/ui/dialog'
import { Input } from '@pricepolicy/ui/components/ui/input'
import { Label } from '@pricepolicy/ui/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@pricepolicy/ui/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@pricepolicy/ui/components/ui/table'
import { toast } from '@pricepolicy/ui/state/toastStore'

import { useSessionStore } from '@/auth/sessionStore'

// ─────────────────────────────────────────────────────────────────────────────
// Trang Quản trị Hệ thống (Admin CP)
// Cấu trúc tài khoản: user | password | email | phone (role phân quyền)
// ─────────────────────────────────────────────────────────────────────────────
export function AdminCpPage() {
  const { data: setupStatus, isLoading: isCheckingStatus, refetch: refetchStatus } = useAdminSetupStatus()
  const currentUser = useSessionStore((s) => s.session?.user)

  if (isCheckingStatus) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <p className="text-sm text-muted-foreground">Đang kiểm tra trạng thái hệ thống...</p>
      </div>
    )
  }

  // 1. Chưa có tài khoản Admin nào trong hệ thống -> Bắt buộc khởi tạo đầu tiên (duy nhất 1 lần)
  if (setupStatus && !setupStatus.initialized) {
    return <InitialAdminSetup onSetupSuccess={() => refetchStatus()} />
  }

  // 2. Đã có Admin nhưng chưa đăng nhập hoặc không phải quyền ADMIN
  if (!currentUser) {
    return <AdminLoginPrompt />
  }

  if (currentUser.role !== 'ADMIN') {
    return <AdminAccessDenied currentRole={currentUser.role} />
  }

  // 3. Đã đăng nhập với tư cách ADMIN -> Hiển thị Bảng điều khiển Quản trị Users
  return <AdminUserManagementDashboard />
}

// ─────────────────────────────────────────────────────────────────────────────
// 1. Màn hình Khởi tạo Quản trị viên ban đầu (Bootstrap First Admin)
// Cấu trúc: user | password | email | phone
// ─────────────────────────────────────────────────────────────────────────────
function InitialAdminSetup({ onSetupSuccess }: { onSetupSuccess: () => void }) {
  const setup = useAdminSetup()
  const setSession = useSessionStore((s) => s.setSession)

  const [user, setUser] = useState('admin')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)

    if (password !== confirmPassword) {
      setError('Mật khẩu xác nhận không khớp.')
      return
    }

    try {
      const payload: InitAdminPayload = {
        user: user.trim(),
        password,
        email: email.trim(),
        phone: phone.trim() || undefined,
      }

      const res = await setup.mutateAsync(payload)

      setSession({
        access_token: res.access_token,
        expires_at: res.expires_at,
        user: {
          user_id: res.user.user ?? res.user.user_id ?? 'admin',
          full_name: res.user.user ?? res.user.full_name ?? 'admin',
          email: res.user.email,
          phone: res.user.phone ?? '',
          role: res.user.role,
          title: 'Quản trị viên hệ thống',
        },
      })

      toast.success('Khởi tạo Quản trị viên đầu tiên thành công!')
      onSetupSuccess()
    } catch (err: any) {
      setError(err?.message || 'Có lỗi xảy ra khi khởi tạo quản trị viên.')
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 p-4">
      <Card className="w-full max-w-lg shadow-xl">
        <CardHeader className="space-y-2 border-b bg-primary/5 pb-6 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-md">
            <ShieldCheck className="h-8 w-8" />
          </div>
          <div className="flex justify-center">
            <Badge variant="outline" className="border-amber-500/50 bg-amber-50 text-amber-700">
              Khởi tạo hệ thống lần đầu (Chỉ 1 lần duy nhất)
            </Badge>
          </div>
          <CardTitle className="font-display text-2xl font-bold">Khởi tạo Quản trị viên (ADMIN)</CardTitle>
          <CardDescription>
            Hệ thống chưa có tài khoản nào. Vui lòng thiết lập tài khoản Quản trị viên đầu tiên để vận hành hệ thống.
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="flex items-center gap-2 rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="space-y-1.5">
              <Label htmlFor="setup-user">Tài khoản (user) *</Label>
              <Input
                id="setup-user"
                required
                placeholder="VD: admin"
                value={user}
                onChange={(e) => setUser(e.target.value)}
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="setup-email">Email *</Label>
                <Input
                  id="setup-email"
                  type="email"
                  required
                  placeholder="admin@vlandfuture.vn"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="setup-phone">Số điện thoại (phone)</Label>
                <Input
                  id="setup-phone"
                  placeholder="0912 345 678"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="setup-pass">Mật khẩu (password) *</Label>
                <Input
                  id="setup-pass"
                  type="password"
                  required
                  placeholder="Tối thiểu 4 ký tự"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="setup-confirm">Xác nhận mật khẩu *</Label>
                <Input
                  id="setup-confirm"
                  type="password"
                  required
                  placeholder="Nhập lại mật khẩu"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
              </div>
            </div>

            <Button type="submit" className="w-full text-base" disabled={setup.isPending}>
              {setup.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Shield className="mr-2 h-4 w-4" />}
              Khởi tạo Quản trị viên & Đăng nhập
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 2. Bảng điều khiển Quản trị Người dùng & Phân quyền (Admin CP Dashboard)
// Cấu trúc hiển thị: user | password | email | phone | role
// ─────────────────────────────────────────────────────────────────────────────
function AdminUserManagementDashboard() {
  const currentUser = useSessionStore((s) => s.session?.user)
  const clearSession = useSessionStore((s) => s.clearSession)

  const [roleFilter, setRoleFilter] = useState<string>('ALL')
  const [search, setSearch] = useState('')
  const [isAddOpen, setIsAddOpen] = useState(false)
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null)
  const [deletingUser, setDeletingUser] = useState<AdminUser | null>(null)

  const queryParams = {
    role: roleFilter === 'ALL' ? undefined : roleFilter,
    search: search.trim() || undefined,
  }

  const { data: users = [], isLoading, refetch } = useAdminUsers(queryParams)
  const createMutation = useCreateUser()
  const updateMutation = useUpdateUser()
  const deleteMutation = useDeleteUser()

  const stats = {
    total: users.length,
    admins: users.filter((u: AdminUser) => u.role === 'ADMIN').length,
    managers: users.filter((u: AdminUser) => u.role === 'MANAGER').length,
    sales: users.filter((u: AdminUser) => u.role === 'SALE').length,
    policyAdmins: users.filter((u: AdminUser) => u.role === 'POLICY_ADMIN').length,
  }

  function roleBadge(role: UserRole) {
    switch (role) {
      case 'ADMIN':
        return <Badge className="bg-purple-600 hover:bg-purple-700">ADMIN</Badge>
      case 'MANAGER':
        return <Badge className="bg-blue-600 hover:bg-blue-700">MANAGER</Badge>
      case 'SALE':
        return <Badge className="bg-emerald-600 hover:bg-emerald-700">SALE</Badge>
      case 'POLICY_ADMIN':
        return <Badge className="bg-amber-600 hover:bg-amber-700">POLICY_ADMIN</Badge>
      default:
        return <Badge variant="outline">{role}</Badge>
    }
  }

  return (
    <div className="space-y-6">
      {/* Banner Action */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-2xl font-bold tracking-tight">Quản trị Người dùng & Phân quyền</h2>
            <Badge variant="outline" className="border-primary/30 text-primary text-xs">
              admin_cp
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            Quản trị danh sách người dùng và phân quyền hệ thống.
          </p>
        </div>
        <Button onClick={() => setIsAddOpen(true)} className="shadow">
          <UserPlus className="mr-2 h-4 w-4" />
          Thêm tài khoản mới
        </Button>
      </div>

        {/* Metric Cards */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
          <Card>
            <CardHeader className="p-4 pb-2">
              <CardDescription className="text-xs">Tổng thành viên</CardDescription>
              <CardTitle className="text-2xl">{stats.total}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="p-4 pb-2">
              <CardDescription className="text-xs text-purple-600 font-semibold">Quản trị viên (ADMIN)</CardDescription>
              <CardTitle className="text-2xl text-purple-600">{stats.admins}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="p-4 pb-2">
              <CardDescription className="text-xs text-blue-600 font-semibold">Quản lý duyệt (MGR)</CardDescription>
              <CardTitle className="text-2xl text-blue-600">{stats.managers}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="p-4 pb-2">
              <CardDescription className="text-xs text-emerald-600 font-semibold">Kinh doanh (SALE)</CardDescription>
              <CardTitle className="text-2xl text-emerald-600">{stats.sales}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="p-4 pb-2">
              <CardDescription className="text-xs text-amber-600 font-semibold">Chính sách (POL_ADM)</CardDescription>
              <CardTitle className="text-2xl text-amber-600">{stats.policyAdmins}</CardTitle>
            </CardHeader>
          </Card>
        </div>

        {/* Lối vào trang chất lượng AI — tách riêng vì khác vai với quản trị tài khoản */}
        <Card className="border-primary/25 bg-primary/[0.03]">
          <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-primary/10">
                <Gauge className="h-4.5 w-4.5 text-primary" />
              </span>
              <div>
                <p className="text-sm font-semibold">Chất lượng Copilot</p>
                <p className="text-xs text-muted-foreground">
                  Theo dõi đánh giá 👍/👎 của Sale: tỉ lệ hài lòng, xu hướng 14 ngày, tool hay bị chê và nội dung
                  từng lượt bị chê (đã che PII khách). Số liệu này cũng được nạp lại vào prompt của trợ lý.
                </p>
              </div>
            </div>
            <Button asChild variant="outline" className="shrink-0">
              <Link to="/admin/copilot-quality">
                Mở trang chất lượng <ExternalLink className="ml-2 h-3.5 w-3.5" />
              </Link>
            </Button>
          </CardContent>
        </Card>

        {/* Filter bar */}
        <Card>
          <CardContent className="p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="relative flex-1 sm:max-w-xs">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Tìm theo user, email, phone..."
                  className="pl-9"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium text-muted-foreground">Lọc vai trò:</span>
                {(['ALL', 'SALE', 'MANAGER', 'POLICY_ADMIN', 'ADMIN'] as const).map((r) => (
                  <Button
                    key={r}
                    variant={roleFilter === r ? 'default' : 'outline'}
                    size="sm"
                    className="h-8 text-xs"
                    onClick={() => setRoleFilter(r)}
                  >
                    {r === 'ALL' ? 'Tất cả' : r}
                  </Button>
                ))}
                <Button variant="ghost" size="sm" className="h-8 px-2" onClick={() => refetch()}>
                  <RefreshCw className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Table of Users: user | password | email | phone | role */}
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[160px]">user (Tài khoản)</TableHead>
                <TableHead className="w-[180px]">password (Mật khẩu)</TableHead>
                <TableHead>email (Email)</TableHead>
                <TableHead>phone (Điện thoại)</TableHead>
                <TableHead className="w-[140px]">role (Phân quyền)</TableHead>
                <TableHead className="text-right w-[120px]">Thao tác</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={6} className="h-32 text-center text-muted-foreground">
                    <Loader2 className="mx-auto h-6 w-6 animate-spin" />
                    Đang tải danh sách người dùng...
                  </TableCell>
                </TableRow>
              ) : users.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="h-32 text-center text-muted-foreground">
                    Không tìm thấy người dùng nào phù hợp.
                  </TableCell>
                </TableRow>
              ) : (
                users.map((u: AdminUser) => {
                  const userName = u.user ?? u.user_id ?? ''
                  return (
                    <TableRow key={userName}>
                      <TableCell className="font-semibold text-foreground font-mono">{userName}</TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground" title={u.password}>
                        {u.password ? `${u.password.slice(0, 10)}...` : '••••••••'}
                      </TableCell>
                      <TableCell className="text-sm">{u.email}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">{u.phone || '—'}</TableCell>
                      <TableCell>{roleBadge(u.role)}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-muted-foreground hover:text-foreground"
                            onClick={() => setEditingUser(u)}
                            title="Sửa / Phân quyền"
                          >
                            <Edit3 className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-destructive/70 hover:bg-destructive/10 hover:text-destructive"
                            onClick={() => setDeletingUser(u)}
                            title="Xóa người dùng"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })
              )}
            </TableBody>
          </Table>
        </Card>

      {/* Modal Thêm Người dùng Mới: user | password | email | phone | role */}
      {isAddOpen && (
        <CreateUserDialog
          open={isAddOpen}
          onClose={() => setIsAddOpen(false)}
          onCreate={async (payload: CreateUserPayload) => {
            await createMutation.mutateAsync(payload)
            toast.success(`Đã tạo thành công tài khoản ${payload.user}`)
            setIsAddOpen(false)
          }}
        />
      )}

      {/* Modal Sửa / Phân quyền Người dùng */}
      {editingUser && (
        <EditUserDialog
          user={editingUser}
          open={Boolean(editingUser)}
          onClose={() => setEditingUser(null)}
          onUpdate={async (userId: string, payload: UpdateUserPayload) => {
            await updateMutation.mutateAsync({ userId, body: payload })
            toast.success('Cập nhật tài khoản thành công!')
            setEditingUser(null)
          }}
        />
      )}

      {/* Modal Xác nhận Xóa */}
      {deletingUser && (
        <Dialog open={Boolean(deletingUser)} onOpenChange={() => setDeletingUser(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="text-destructive flex items-center gap-2">
                <Trash2 className="h-5 w-5" />
                Xác nhận xóa tài khoản
              </DialogTitle>
              <DialogDescription>
                Bạn có chắc chắn muốn xóa tài khoản <strong>{deletingUser.user ?? deletingUser.user_id}</strong> ({deletingUser.email})? Thao tác này không thể hoàn tác.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter className="gap-2 sm:gap-0">
              <Button variant="outline" onClick={() => setDeletingUser(null)}>
                Hủy bỏ
              </Button>
              <Button
                variant="destructive"
                disabled={deleteMutation.isPending}
                onClick={async () => {
                  try {
                    const targetId = deletingUser.user ?? deletingUser.user_id ?? ''
                    await deleteMutation.mutateAsync(targetId)
                    toast.success(`Đã xóa tài khoản ${targetId}`)
                    setDeletingUser(null)
                  } catch (err: any) {
                    toast.error(err?.message || 'Không thể xóa tài khoản.')
                  }
                }}
              >
                {deleteMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Xác nhận xóa
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 3. Modal Thêm User Mới (user | password | email | phone | role)
// ─────────────────────────────────────────────────────────────────────────────
function CreateUserDialog({
  open,
  onClose,
  onCreate,
}: {
  open: boolean
  onClose: () => void
  onCreate: (payload: CreateUserPayload) => Promise<void>
}) {
  const [user, setUser] = useState('')
  const [password, setPassword] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [role, setRole] = useState<UserRole>('SALE')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await onCreate({
        user: user.trim(),
        password,
        email: email.trim(),
        phone: phone.trim() || undefined,
        role,
      })
    } catch (err: any) {
      setError(err?.message || 'Có lỗi xảy ra khi tạo người dùng.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <UserPlus className="h-5 w-5 text-primary" />
            Thêm tài khoản người dùng mới
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 py-2">
          {error && <p className="text-xs text-destructive">{error}</p>}

          <div className="space-y-1.5">
            <Label htmlFor="create-user">Tài khoản (user) *</Label>
            <Input
              id="create-user"
              required
              placeholder="VD: sale01"
              value={user}
              onChange={(e) => setUser(e.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="create-pass">Mật khẩu (password) *</Label>
            <Input
              id="create-pass"
              type="password"
              required
              placeholder="Tối thiểu 4 ký tự"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="create-email">Email *</Label>
            <Input
              id="create-email"
              type="email"
              required
              placeholder="VD: sale01@vlandfuture.vn"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="create-phone">Số điện thoại (phone)</Label>
              <Input
                id="create-phone"
                placeholder="VD: 0987 654 321"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="create-role">Phân quyền (role)</Label>
              <Select value={role} onValueChange={(v: string) => setRole(v as UserRole)}>
                <SelectTrigger id="create-role">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="SALE">SALE (Kinh doanh)</SelectItem>
                  <SelectItem value="MANAGER">MANAGER (Quản lý duyệt)</SelectItem>
                  <SelectItem value="POLICY_ADMIN">POLICY_ADMIN (Chính sách)</SelectItem>
                  <SelectItem value="ADMIN">ADMIN (Quản trị viên)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <DialogFooter className="pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Hủy
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Tạo tài khoản
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 4. Modal Sửa / Phân quyền User (user | password | email | phone | role)
// ─────────────────────────────────────────────────────────────────────────────
function EditUserDialog({
  user,
  open,
  onClose,
  onUpdate,
}: {
  user: AdminUser
  open: boolean
  onClose: () => void
  onUpdate: (userId: string, payload: UpdateUserPayload) => Promise<void>
}) {
  const userName = user.user ?? user.user_id ?? ''
  const [email, setEmail] = useState(user.email)
  const [phone, setPhone] = useState(user.phone || '')
  const [role, setRole] = useState<UserRole>(user.role)
  const [newPassword, setNewPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      const payload: UpdateUserPayload = {
        email: email.trim(),
        phone: phone.trim() || undefined,
        role,
      }
      if (newPassword.trim()) {
        payload.password = newPassword.trim()
      }
      await onUpdate(userName, payload)
    } catch (err: any) {
      setError(err?.message || 'Có lỗi xảy ra khi cập nhật người dùng.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Edit3 className="h-5 w-5 text-primary" />
            Cập nhật tài khoản & Phân quyền
          </DialogTitle>
          <DialogDescription>
            Đang chỉnh sửa: <strong>{userName}</strong> ({user.email})
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 py-2">
          {error && <p className="text-xs text-destructive">{error}</p>}

          <div className="space-y-1.5">
            <Label htmlFor="edit-user">Tài khoản (user)</Label>
            <Input id="edit-user" disabled value={userName} className="bg-muted font-mono" />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="edit-email">Email</Label>
            <Input id="edit-email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="edit-phone">Số điện thoại (phone)</Label>
              <Input id="edit-phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="edit-role">Phân quyền (role)</Label>
              <Select value={role} onValueChange={(v: string) => setRole(v as UserRole)}>
                <SelectTrigger id="edit-role">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="SALE">SALE</SelectItem>
                  <SelectItem value="MANAGER">MANAGER</SelectItem>
                  <SelectItem value="POLICY_ADMIN">POLICY_ADMIN</SelectItem>
                  <SelectItem value="ADMIN">ADMIN</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="edit-pass">Đổi mật khẩu mới (password)</Label>
            <Input
              id="edit-pass"
              type="password"
              placeholder="Để trống nếu không đổi mật khẩu"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
          </div>

          <DialogFooter className="pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Hủy
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Lưu thay đổi
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 5. Màn hình Nhắc Đăng nhập / Từ chối truy cập
// ─────────────────────────────────────────────────────────────────────────────
function AdminLoginPrompt() {
  const navigate = useNavigate()
  return (
    <div className="flex min-h-[70vh] items-center justify-center p-4">
      <Card className="max-w-md text-center shadow-lg">
        <CardHeader className="space-y-2">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
            <Lock className="h-6 w-6" />
          </div>
          <CardTitle className="text-xl">Yêu cầu Đăng nhập Quản trị viên</CardTitle>
          <CardDescription>
            Trang <strong>admin_cp</strong> yêu cầu phiên đăng nhập của tài khoản có phân quyền <code>ADMIN</code>.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Button className="w-full" onClick={() => navigate('/login')}>
            Đến trang Đăng nhập
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}

function AdminAccessDenied({ currentRole }: { currentRole: string }) {
  const clearSession = useSessionStore((s) => s.clearSession)
  const navigate = useNavigate()

  return (
    <div className="flex min-h-[70vh] items-center justify-center p-4">
      <Card className="max-w-md text-center shadow-lg border-destructive/20">
        <CardHeader className="space-y-2">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10 text-destructive">
            <ShieldAlert className="h-6 w-6" />
          </div>
          <CardTitle className="text-xl text-destructive">Truy cập bị từ chối</CardTitle>
          <CardDescription>
            Bạn đang đăng nhập với vai trò <strong>{currentRole}</strong>. Chỉ tài khoản <strong>ADMIN</strong> mới có quyền truy cập trang quản trị này.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Button variant="outline" className="w-full" onClick={() => navigate('/workspace')}>
            Quay lại Workspace của tôi
          </Button>
          <Button
            variant="ghost"
            className="w-full text-destructive hover:bg-destructive/10"
            onClick={() => {
              clearSession()
              navigate('/login')
            }}
          >
            Đăng xuất để đổi tài khoản
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
