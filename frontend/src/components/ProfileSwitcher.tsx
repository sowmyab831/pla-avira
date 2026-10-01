import { useEffect, useState } from 'react'
import { User, Users } from 'lucide-react'
import { familyApi } from '../api/nexus'

export interface Profile {
  id: string        // 'self' or family member id
  name: string
  userId: string    // partition key passed as ?user_id= to finance/health APIs
}

const SELF: Profile = { id: 'self', name: 'Myself', userId: 'default' }
const STORAGE_KEY = 'avira_profile'

export function getActiveProfile(): Profile {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const p = JSON.parse(raw)
      if (p && p.userId) return p
    }
  } catch { /* ignore */ }
  return SELF
}

export function setActiveProfile(p: Profile) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(p))
}

/**
 * Dropdown to switch the active data profile: "Myself" or a family member.
 * Member profiles store their health/finance data under user_id `member_<id>`
 * (their own directory in document storage).
 */
export default function ProfileSwitcher({ onChange }: { onChange?: (p: Profile) => void }) {
  const [profiles, setProfiles] = useState<Profile[]>([SELF])
  const [active, setActive] = useState<Profile>(getActiveProfile())

  useEffect(() => {
    familyApi.members()
      .then((d: any) => {
        const ms: Profile[] = (d.members || []).map((m: any) => ({
          id: m.id,
          name: m.name,
          userId: `member_${m.id}`,
        }))
        setProfiles([SELF, ...ms])
        // If saved profile no longer exists, fall back to self
        const saved = getActiveProfile()
        const valid = saved.id === 'self' || ms.some(m => m.id === saved.id)
        const next = valid ? saved : SELF
        setActive(next)
        if (!valid) setActiveProfile(SELF)
      })
      .catch(() => { /* not logged in or no members — self only */ })
  }, [])

  const choose = (id: string) => {
    const p = profiles.find(x => x.id === id) || SELF
    setActive(p)
    setActiveProfile(p)
    onChange?.(p)
  }

  return (
    <div className="flex items-center gap-2">
      {active.id === 'self'
        ? <User size={16} className="text-gray-500" />
        : <Users size={16} className="text-indigo-500" />}
      <select
        value={active.id}
        onChange={e => choose(e.target.value)}
        className="text-sm border border-gray-200 rounded-lg px-2 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-300"
        title="Choose whose data to view/manage"
      >
        {profiles.map(p => (
          <option key={p.id} value={p.id}>{p.name}{p.id === 'self' ? '' : ' (family)'}</option>
        ))}
      </select>
    </div>
  )
}
