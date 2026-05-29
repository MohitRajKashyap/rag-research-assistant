import React, { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  MessageSquare, FileText, FolderOpen, LayoutDashboard,
  Settings, LogOut, Moon, Sun, Menu, X, Shield, Search,
  ChevronLeft, Zap,
} from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { useDarkMode } from '@/hooks/useDarkMode'
import { cn } from '@/utils/helpers'

interface NavItem {
  icon: React.ReactNode
  label: string
  href: string
  adminOnly?: boolean
}

const NAV_ITEMS: NavItem[] = [
  { icon: <MessageSquare size={18} />, label: 'Chat', href: '/chat' },
  { icon: <FileText size={18} />, label: 'Documents', href: '/documents' },
  { icon: <Search size={18} />, label: 'Search', href: '/search' },
  { icon: <FolderOpen size={18} />, label: 'Collections', href: '/collections' },
  { icon: <LayoutDashboard size={18} />, label: 'Dashboard', href: '/dashboard' },
  { icon: <Shield size={18} />, label: 'Admin', href: '/admin', adminOnly: true },
  { icon: <Settings size={18} />, label: 'Settings', href: '/settings' },
]

interface LayoutProps {
  children: React.ReactNode
}

export function AppLayout({ children }: LayoutProps) {
  const { user, logout } = useAuthStore()
  const { isDark, toggle: toggleDark } = useDarkMode()
  const location = useLocation()
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [mobileOpen, setMobileOpen] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const navItems = NAV_ITEMS.filter((item) => !item.adminOnly || user?.role === 'admin')

  const SidebarContent = () => (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="flex items-center gap-2 px-4 py-5 border-b border-gray-200 dark:border-gray-700">
        <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center flex-shrink-0">
          <Zap size={16} className="text-white" />
        </div>
        <AnimatePresence>
          {sidebarOpen && (
            <motion.div
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: 1, width: 'auto' }}
              exit={{ opacity: 0, width: 0 }}
              transition={{ duration: 0.15 }}
              className="overflow-hidden"
            >
              <span className="font-bold text-gray-900 dark:text-white whitespace-nowrap text-sm">
                RAG Research
              </span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Nav items */}
      <nav className="flex-1 px-2 py-4 space-y-0.5 overflow-y-auto">
        {navItems.map((item) => {
          const active = location.pathname.startsWith(item.href)
          return (
            <Link
              key={item.href}
              to={item.href}
              onClick={() => setMobileOpen(false)}
              className={cn(
                'flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-150 group',
                active
                  ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300'
                  : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-white',
              )}
            >
              <span className={cn('flex-shrink-0', active ? 'text-primary-600' : '')}>{item.icon}</span>
              <AnimatePresence>
                {sidebarOpen && (
                  <motion.span
                    initial={{ opacity: 0, width: 0 }}
                    animate={{ opacity: 1, width: 'auto' }}
                    exit={{ opacity: 0, width: 0 }}
                    transition={{ duration: 0.15 }}
                    className="text-sm font-medium whitespace-nowrap overflow-hidden"
                  >
                    {item.label}
                  </motion.span>
                )}
              </AnimatePresence>
            </Link>
          )
        })}
      </nav>

      {/* Bottom: user info + controls */}
      <div className="px-2 pb-4 border-t border-gray-200 dark:border-gray-700 pt-4 space-y-1">
        <button
          onClick={toggleDark}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        >
          {isDark ? <Sun size={18} /> : <Moon size={18} />}
          {sidebarOpen && <span className="text-sm font-medium">{isDark ? 'Light mode' : 'Dark mode'}</span>}
        </button>

        {sidebarOpen && user && (
          <div className="flex items-center gap-3 px-3 py-2 rounded-lg bg-gray-50 dark:bg-gray-800 mt-2">
            <div className="w-7 h-7 rounded-full bg-primary-600 flex items-center justify-center flex-shrink-0">
              <span className="text-xs font-bold text-white uppercase">
                {user.username?.charAt(0)}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-gray-900 dark:text-white truncate">{user.username}</p>
              <p className="text-xs text-gray-500 truncate">{user.role}</p>
            </div>
          </div>
        )}

        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
        >
          <LogOut size={18} />
          {sidebarOpen && <span className="text-sm font-medium">Sign out</span>}
        </button>
      </div>
    </div>
  )

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-950 overflow-hidden">
      {/* Desktop sidebar */}
      <aside
        className={cn(
          'hidden lg:flex flex-col border-r border-gray-200 dark:border-gray-700',
          'bg-white dark:bg-gray-900 transition-all duration-200',
          sidebarOpen ? 'w-56' : 'w-16',
        )}
      >
        <SidebarContent />
        {/* Collapse toggle */}
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="absolute left-0 bottom-24 ml-[calc(100%-12px)] z-10 hidden lg:flex w-6 h-6 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-full items-center justify-center shadow-sm hover:shadow-md transition-all"
          style={{ marginLeft: sidebarOpen ? '212px' : '52px' }}
        >
          <ChevronLeft size={12} className={cn('transition-transform', !sidebarOpen && 'rotate-180')} />
        </button>
      </aside>

      {/* Mobile sidebar overlay */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/50 z-40 lg:hidden"
              onClick={() => setMobileOpen(false)}
            />
            <motion.aside
              initial={{ x: -256 }}
              animate={{ x: 0 }}
              exit={{ x: -256 }}
              transition={{ type: 'spring', damping: 25, stiffness: 200 }}
              className="fixed inset-y-0 left-0 w-64 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700 z-50 flex flex-col lg:hidden"
            >
              <SidebarContent />
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Mobile header */}
        <header className="lg:hidden flex items-center gap-4 px-4 py-3 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
          <button
            onClick={() => setMobileOpen(true)}
            className="p-2 rounded-lg text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
          >
            <Menu size={20} />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 bg-primary-600 rounded flex items-center justify-center">
              <Zap size={12} className="text-white" />
            </div>
            <span className="font-bold text-sm text-gray-900 dark:text-white">RAG Research</span>
          </div>
        </header>

        <main className="flex-1 overflow-hidden">{children}</main>
      </div>
    </div>
  )
}
