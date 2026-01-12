import { Link, Outlet, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  Mail,
  History,
  Settings,
  LogOut,
  Menu,
  Users,
  Building2,
} from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { useAuth } from '@/hooks/useAuth'

interface NavItem {
  name: string
  href: string
  icon: React.ComponentType<{ className?: string }>
  adminOnly?: boolean
}

const navigation: NavItem[] = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Message Traces', href: '/traces', icon: Mail },
  { name: 'Pull History', href: '/pull-history', icon: History },
  { name: 'Users', href: '/users', icon: Users, adminOnly: true },
  { name: 'Tenants', href: '/tenants', icon: Building2, adminOnly: true },
  { name: 'Settings', href: '/settings', icon: Settings },
]

export function Layout() {
  const location = useLocation()
  const { logout, isAdmin } = useAuth()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Filter navigation items based on admin status
  const visibleNavigation = navigation.filter(
    (item) => !item.adminOnly || isAdmin
  )

  return (
    <div className="min-h-screen bg-background">
      {/* Mobile sidebar toggle */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-40 flex h-16 items-center gap-4 border-b bg-background px-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setSidebarOpen(!sidebarOpen)}
        >
          <Menu className="h-6 w-6" />
        </Button>
        <span className="font-semibold">Exo-Trace-Archiver</span>
      </div>

      {/* Sidebar */}
      <div
        className={cn(
          'fixed inset-y-0 left-0 z-50 w-64 bg-card border-r transform transition-transform duration-200 ease-in-out lg:translate-x-0',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="flex h-16 items-center px-6 border-b">
          <Link to="/" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-bold">
              E
            </div>
            <span className="font-semibold text-lg">Exo-Trace</span>
          </Link>
        </div>

        <nav className="flex-1 space-y-1 px-3 py-4">
          {visibleNavigation.map((item) => {
            const isActive =
              item.href === '/'
                ? location.pathname === '/'
                : location.pathname.startsWith(item.href)
            return (
              <Link
                key={item.name}
                to={item.href}
                onClick={() => setSidebarOpen(false)}
                className={cn(
                  'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                )}
              >
                <item.icon className="h-5 w-5" />
                {item.name}
              </Link>
            )
          })}
        </nav>

        <div className="border-t p-3">
          <Button
            variant="ghost"
            className="w-full justify-start gap-3 text-muted-foreground"
            onClick={logout}
          >
            <LogOut className="h-5 w-5" />
            Sign out
          </Button>
        </div>
      </div>

      {/* Overlay for mobile */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main content */}
      <div className="lg:pl-64">
        <main className="py-6 px-4 lg:px-8 mt-16 lg:mt-0">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
