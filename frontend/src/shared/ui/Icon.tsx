/**
 * The icon set -- Lucide, at the 2px outline weight the design system chose for
 * sitting closest to the crest's line work (ADR-074).
 *
 * A dependency rather than copied SVG paths, and the distinction from `C23` is
 * the point: shadcn is *design opinion* expressed as markup, so it is copied and
 * owned. An icon is **geometry** -- there is no version of `building-2` that is
 * ours -- and forty path strings written from memory would be forty glyphs that
 * look almost right. Pinned exactly, like everything else.
 *
 * Names are the design system's, kebab-case, so a name read off the mock is the
 * name written here. The union is the whole vocabulary: an icon nothing renders
 * is an icon nobody chose.
 */

import {
  ArrowDown,
  Bell,
  ArrowDownUp,
  ArrowUp,
  BookOpen,
  Briefcase,
  Building2,
  CalendarDays,
  Check,
  ChevronDown,
  CircleHelp,
  ChevronsUpDown,
  ClipboardList,
  Coins,
  Copy,
  Download,
  FilePen,
  FilePlus,
  FileText,
  Import,
  Layers,
  LayoutDashboard,
  Library,
  ListTree,
  Lock,
  LogOut,
  Mail,
  Plus,
  Receipt,
  Scale,
  Search,
  Shield,
  TriangleAlert,
  Users,
  X,
  type LucideIcon,
} from 'lucide-react'

const ICONS = {
  'arrow-down': ArrowDown,
  'arrow-down-up': ArrowDownUp,
  'arrow-up': ArrowUp,
  bell: Bell,
  'book-open': BookOpen,
  briefcase: Briefcase,
  'building-2': Building2,
  'calendar-days': CalendarDays,
  check: Check,
  'chevron-down': ChevronDown,
  'chevrons-up-down': ChevronsUpDown,
  'circle-help': CircleHelp,
  'clipboard-list': ClipboardList,
  coins: Coins,
  copy: Copy,
  download: Download,
  'file-pen': FilePen,
  'file-plus': FilePlus,
  'file-text': FileText,
  import: Import,
  layers: Layers,
  'layout-dashboard': LayoutDashboard,
  library: Library,
  'list-tree': ListTree,
  lock: Lock,
  'log-out': LogOut,
  mail: Mail,
  plus: Plus,
  receipt: Receipt,
  scale: Scale,
  search: Search,
  shield: Shield,
  'triangle-alert': TriangleAlert,
  users: Users,
  x: X,
} satisfies Record<string, LucideIcon>

export type IconName = keyof typeof ICONS

export function Icon({
  name,
  size = 18,
  label,
  className,
}: {
  name: IconName
  size?: number
  /** Give one only when the icon is the whole meaning. Beside a word, it is decoration. */
  label?: string
  className?: string
}) {
  const Glyph = ICONS[name]
  return (
    <Glyph
      size={size}
      strokeWidth={2}
      className={className}
      aria-hidden={label ? undefined : true}
      aria-label={label}
      role={label ? 'img' : undefined}
    />
  )
}
