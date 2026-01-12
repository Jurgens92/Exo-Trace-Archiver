import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Building2,
  Plus,
  Edit2,
  Trash2,
  RefreshCw,
  AlertCircle,
  Users,
  Check,
  X,
  Plug,
  Upload,
  FileKey,
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { LoadingPage, LoadingSpinner } from '@/components/LoadingSpinner'
import { useToast } from '@/components/ui/use-toast'
import { useAuth } from '@/hooks/useAuth'
import {
  getTenants,
  createTenant,
  updateTenant,
  deleteTenant,
  testTenantConnection,
  uploadCertificate,
} from '@/api/tenants'
import type { Tenant, TenantCreate, TenantUpdate } from '@/api/types'

export function TenantsPage() {
  const { isAdmin } = useAuth()
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [editingTenant, setEditingTenant] = useState<Tenant | null>(null)

  const { data: tenantsData, isLoading, error, refetch } = useQuery({
    queryKey: ['tenants', search],
    queryFn: () => getTenants({ search: search || undefined }),
    enabled: isAdmin,
  })

  const createMutation = useMutation({
    mutationFn: createTenant,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenants'] })
      setShowCreateForm(false)
      toast({ title: 'Tenant created successfully' })
    },
    onError: () => {
      toast({ title: 'Failed to create tenant', variant: 'destructive' })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: TenantUpdate }) => updateTenant(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenants'] })
      setEditingTenant(null)
      toast({ title: 'Tenant updated successfully' })
    },
    onError: () => {
      toast({ title: 'Failed to update tenant', variant: 'destructive' })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteTenant,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenants'] })
      toast({ title: 'Tenant deleted successfully' })
    },
    onError: () => {
      toast({ title: 'Failed to delete tenant', variant: 'destructive' })
    },
  })

  const testConnectionMutation = useMutation({
    mutationFn: testTenantConnection,
    onSuccess: (data) => {
      toast({
        title: data.status === 'success' ? 'Connection successful' : 'Connection failed',
        description: data.detail,
        variant: data.status === 'success' ? 'default' : 'destructive',
      })
    },
    onError: () => {
      toast({ title: 'Connection test failed', variant: 'destructive' })
    },
  })

  if (!isAdmin) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold">Tenant Management</h1>
        <Card>
          <CardContent className="py-12 text-center">
            <AlertCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
            <p className="text-muted-foreground">
              You need administrator permissions to access this page.
            </p>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (isLoading) return <LoadingPage />

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold">Tenant Management</h1>
        <Card>
          <CardContent className="py-12 text-center">
            <AlertCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
            <p className="text-destructive mb-4">Failed to load tenants.</p>
            <Button onClick={() => refetch()}>Retry</Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  const tenants = tenantsData?.results || []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold flex items-center gap-3">
          <Building2 className="h-8 w-8" />
          Tenant Management
        </h1>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button onClick={() => setShowCreateForm(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Add Tenant
          </Button>
        </div>
      </div>

      {/* Search */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex gap-4">
            <Input
              placeholder="Search tenants..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="max-w-sm"
            />
          </div>
        </CardContent>
      </Card>

      {/* Create Tenant Form */}
      {showCreateForm && (
        <CreateTenantForm
          onSubmit={(data) => createMutation.mutate(data)}
          onCancel={() => setShowCreateForm(false)}
          isLoading={createMutation.isPending}
        />
      )}

      {/* Edit Tenant Form */}
      {editingTenant && (
        <EditTenantForm
          tenant={editingTenant}
          onSubmit={(data) => updateMutation.mutate({ id: editingTenant.id, data })}
          onCancel={() => setEditingTenant(null)}
          isLoading={updateMutation.isPending}
        />
      )}

      {/* Tenants Table */}
      <Card>
        <CardHeader>
          <CardTitle>MS365 Tenants ({tenants.length})</CardTitle>
          <CardDescription>
            Manage Microsoft 365 tenant connections for message trace collection
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Organization</TableHead>
                <TableHead>Auth Method</TableHead>
                <TableHead>API</TableHead>
                <TableHead>Users</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tenants.map((tenant) => (
                <TableRow key={tenant.id}>
                  <TableCell className="font-medium">{tenant.name}</TableCell>
                  <TableCell className="font-mono text-sm">
                    {tenant.organization || '-'}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{tenant.auth_method}</Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary">{tenant.api_method}</Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <Users className="h-4 w-4 text-muted-foreground" />
                      {tenant.user_count ?? 0}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant={tenant.is_active ? 'default' : 'destructive'}>
                      {tenant.is_active ? (
                        <><Check className="h-3 w-3 mr-1" /> Active</>
                      ) : (
                        <><X className="h-3 w-3 mr-1" /> Inactive</>
                      )}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => testConnectionMutation.mutate(tenant.id)}
                        disabled={testConnectionMutation.isPending}
                        title="Test connection"
                      >
                        <Plug className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setEditingTenant(tenant)}
                      >
                        <Edit2 className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          if (confirm(`Delete tenant ${tenant.name}? This will also delete all associated message traces.`)) {
                            deleteMutation.mutate(tenant.id)
                          }
                        }}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {tenants.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                    No tenants configured. Add a tenant to start collecting message traces.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}

interface CreateTenantFormProps {
  onSubmit: (data: TenantCreate) => void
  onCancel: () => void
  isLoading: boolean
}

function CreateTenantForm({ onSubmit, onCancel, isLoading }: CreateTenantFormProps) {
  const { toast } = useToast()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [formData, setFormData] = useState<TenantCreate>({
    name: '',
    tenant_id: '',
    client_id: '',
    auth_method: 'certificate',
    api_method: 'graph',
    organization: '',
    is_active: true,
  })
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState(false)

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    // Validate file extension
    const allowedExtensions = ['.pfx', '.pem', '.cer', '.crt', '.p12']
    const fileExt = file.name.toLowerCase().substring(file.name.lastIndexOf('.'))
    if (!allowedExtensions.includes(fileExt)) {
      toast({
        title: 'Invalid file type',
        description: `Allowed types: ${allowedExtensions.join(', ')}`,
        variant: 'destructive',
      })
      return
    }

    setIsUploading(true)
    try {
      const result = await uploadCertificate(file)
      setFormData({
        ...formData,
        certificate_path: result.certificate_path,
        certificate_thumbprint: result.certificate_thumbprint || formData.certificate_thumbprint,
      })
      setUploadedFileName(file.name)
      toast({
        title: 'Certificate uploaded',
        description: result.certificate_thumbprint
          ? `Thumbprint: ${result.certificate_thumbprint.substring(0, 16)}...`
          : 'Certificate saved successfully',
      })
    } catch {
      toast({
        title: 'Upload failed',
        description: 'Failed to upload certificate file',
        variant: 'destructive',
      })
    } finally {
      setIsUploading(false)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit(formData)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Add New Tenant</CardTitle>
        <CardDescription>
          Configure a new Microsoft 365 tenant for message trace collection
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="name">Display Name *</Label>
              <Input
                id="name"
                placeholder="e.g., Contoso Production"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="organization">Organization Domain</Label>
              <Input
                id="organization"
                placeholder="e.g., contoso.onmicrosoft.com"
                value={formData.organization}
                onChange={(e) => setFormData({ ...formData, organization: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="tenant_id">Tenant ID (GUID) *</Label>
              <Input
                id="tenant_id"
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                value={formData.tenant_id}
                onChange={(e) => setFormData({ ...formData, tenant_id: e.target.value })}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="client_id">Client ID (GUID) *</Label>
              <Input
                id="client_id"
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                value={formData.client_id}
                onChange={(e) => setFormData({ ...formData, client_id: e.target.value })}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="auth_method">Authentication Method</Label>
              <Select
                value={formData.auth_method}
                onValueChange={(value: 'certificate' | 'secret') =>
                  setFormData({ ...formData, auth_method: value })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="certificate">Certificate</SelectItem>
                  <SelectItem value="secret">Client Secret</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="api_method">API Method</Label>
              <Select
                value={formData.api_method}
                onValueChange={(value: 'graph' | 'powershell') =>
                  setFormData({ ...formData, api_method: value })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="graph">Microsoft Graph API</SelectItem>
                  <SelectItem value="powershell">Exchange PowerShell</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {formData.auth_method === 'certificate' && (
              <>
                <div className="space-y-2 md:col-span-2">
                  <Label>Certificate File *</Label>
                  <div className="flex items-center gap-2">
                    <input
                      type="file"
                      ref={fileInputRef}
                      onChange={handleFileUpload}
                      accept=".pfx,.pem,.cer,.crt,.p12"
                      className="hidden"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={isUploading}
                      className="flex-shrink-0"
                    >
                      {isUploading ? (
                        <LoadingSpinner size="sm" className="mr-2" />
                      ) : (
                        <Upload className="h-4 w-4 mr-2" />
                      )}
                      Upload Certificate
                    </Button>
                    {uploadedFileName && (
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <FileKey className="h-4 w-4" />
                        <span className="truncate max-w-[200px]">{uploadedFileName}</span>
                        <Check className="h-4 w-4 text-green-500" />
                      </div>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Supported formats: .pfx, .pem, .cer, .crt, .p12
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="certificate_thumbprint">Certificate Thumbprint</Label>
                  <Input
                    id="certificate_thumbprint"
                    placeholder="Auto-detected or enter manually"
                    value={formData.certificate_thumbprint || ''}
                    onChange={(e) => setFormData({ ...formData, certificate_thumbprint: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="certificate_password">Certificate Password</Label>
                  <Input
                    id="certificate_password"
                    type="password"
                    placeholder="If password-protected"
                    value={formData.certificate_password || ''}
                    onChange={(e) => setFormData({ ...formData, certificate_password: e.target.value })}
                  />
                </div>
              </>
            )}

            {formData.auth_method === 'secret' && (
              <div className="space-y-2">
                <Label htmlFor="client_secret">Client Secret *</Label>
                <Input
                  id="client_secret"
                  type="password"
                  value={formData.client_secret || ''}
                  onChange={(e) => setFormData({ ...formData, client_secret: e.target.value })}
                  required={formData.auth_method === 'secret'}
                />
              </div>
            )}
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onCancel}>
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading || isUploading}>
              {isLoading ? <LoadingSpinner size="sm" className="mr-2" /> : null}
              Create Tenant
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

interface EditTenantFormProps {
  tenant: Tenant
  onSubmit: (data: TenantUpdate) => void
  onCancel: () => void
  isLoading: boolean
}

function EditTenantForm({ tenant, onSubmit, onCancel, isLoading }: EditTenantFormProps) {
  const { toast } = useToast()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [formData, setFormData] = useState<TenantUpdate>({
    name: tenant.name,
    organization: tenant.organization,
    auth_method: tenant.auth_method,
    api_method: tenant.api_method,
    is_active: tenant.is_active,
    certificate_path: tenant.certificate_path,
    certificate_thumbprint: tenant.certificate_thumbprint,
  })
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState(false)

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    // Validate file extension
    const allowedExtensions = ['.pfx', '.pem', '.cer', '.crt', '.p12']
    const fileExt = file.name.toLowerCase().substring(file.name.lastIndexOf('.'))
    if (!allowedExtensions.includes(fileExt)) {
      toast({
        title: 'Invalid file type',
        description: `Allowed types: ${allowedExtensions.join(', ')}`,
        variant: 'destructive',
      })
      return
    }

    setIsUploading(true)
    try {
      const result = await uploadCertificate(file)
      setFormData({
        ...formData,
        certificate_path: result.certificate_path,
        certificate_thumbprint: result.certificate_thumbprint || formData.certificate_thumbprint,
      })
      setUploadedFileName(file.name)
      toast({
        title: 'Certificate uploaded',
        description: result.certificate_thumbprint
          ? `Thumbprint: ${result.certificate_thumbprint.substring(0, 16)}...`
          : 'Certificate saved successfully',
      })
    } catch {
      toast({
        title: 'Upload failed',
        description: 'Failed to upload certificate file',
        variant: 'destructive',
      })
    } finally {
      setIsUploading(false)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit(formData)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Edit Tenant: {tenant.name}</CardTitle>
        <CardDescription>
          Tenant ID: {tenant.tenant_id}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="edit_name">Display Name</Label>
              <Input
                id="edit_name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit_organization">Organization Domain</Label>
              <Input
                id="edit_organization"
                value={formData.organization}
                onChange={(e) => setFormData({ ...formData, organization: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit_auth_method">Authentication Method</Label>
              <Select
                value={formData.auth_method}
                onValueChange={(value: 'certificate' | 'secret') =>
                  setFormData({ ...formData, auth_method: value })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="certificate">Certificate</SelectItem>
                  <SelectItem value="secret">Client Secret</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit_api_method">API Method</Label>
              <Select
                value={formData.api_method}
                onValueChange={(value: 'graph' | 'powershell') =>
                  setFormData({ ...formData, api_method: value })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="graph">Microsoft Graph API</SelectItem>
                  <SelectItem value="powershell">Exchange PowerShell</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit_is_active">Status</Label>
              <Select
                value={formData.is_active ? 'active' : 'inactive'}
                onValueChange={(value) => setFormData({ ...formData, is_active: value === 'active' })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="inactive">Inactive</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {formData.auth_method === 'certificate' && (
              <>
                <div className="space-y-2 md:col-span-2">
                  <Label>Certificate File</Label>
                  <div className="flex items-center gap-2">
                    <input
                      type="file"
                      ref={fileInputRef}
                      onChange={handleFileUpload}
                      accept=".pfx,.pem,.cer,.crt,.p12"
                      className="hidden"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={isUploading}
                      className="flex-shrink-0"
                    >
                      {isUploading ? (
                        <LoadingSpinner size="sm" className="mr-2" />
                      ) : (
                        <Upload className="h-4 w-4 mr-2" />
                      )}
                      Upload New Certificate
                    </Button>
                    {uploadedFileName ? (
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <FileKey className="h-4 w-4" />
                        <span className="truncate max-w-[200px]">{uploadedFileName}</span>
                        <Check className="h-4 w-4 text-green-500" />
                      </div>
                    ) : tenant.has_certificate ? (
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <FileKey className="h-4 w-4" />
                        <span>Certificate configured</span>
                        <Check className="h-4 w-4 text-green-500" />
                      </div>
                    ) : null}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Supported formats: .pfx, .pem, .cer, .crt, .p12
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="edit_certificate_thumbprint">Certificate Thumbprint</Label>
                  <Input
                    id="edit_certificate_thumbprint"
                    placeholder="Auto-detected or enter manually"
                    value={formData.certificate_thumbprint || ''}
                    onChange={(e) => setFormData({ ...formData, certificate_thumbprint: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="edit_certificate_password">Certificate Password</Label>
                  <Input
                    id="edit_certificate_password"
                    type="password"
                    placeholder="Leave blank to keep current"
                    onChange={(e) => setFormData({ ...formData, certificate_password: e.target.value || undefined })}
                  />
                </div>
              </>
            )}

            {formData.auth_method === 'secret' && (
              <div className="space-y-2">
                <Label htmlFor="edit_client_secret">New Client Secret</Label>
                <Input
                  id="edit_client_secret"
                  type="password"
                  placeholder="Leave blank to keep current"
                  onChange={(e) => setFormData({ ...formData, client_secret: e.target.value || undefined })}
                />
              </div>
            )}
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onCancel}>
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading || isUploading}>
              {isLoading ? <LoadingSpinner size="sm" className="mr-2" /> : null}
              Save Changes
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
