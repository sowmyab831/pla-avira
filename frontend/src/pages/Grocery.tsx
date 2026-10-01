import { useState, useEffect, useCallback } from 'react'
import { UtensilsCrossed, Calendar, ShoppingCart, RefreshCw, Clock, Flame, ChevronRight, X, ChefHat, Leaf, Dumbbell } from 'lucide-react'
import client from '../api/client'

type Tab = 'plan' | 'recipes'
type Diet = 'any' | 'vegetarian' | 'vegan'

interface Recipe {
  recipe_id: string; name: string; description: string; ingredients: string[]; instructions: string[]
  prep_time_minutes: number; cook_time_minutes: number; servings: number; calories_per_serving: number
  protein_grams: number; carbs_grams: number; fat_grams: number; dietary_tags: string[]; difficulty: string
}

interface MealDay {
  date: string; breakfast: string | null; breakfast_calories: number | null; breakfast_recipe_url: string | null
  lunch: string | null; lunch_calories: number | null; lunch_recipe_url: string | null
  dinner: string | null; dinner_calories: number | null; dinner_recipe_url: string | null
  total_calories: number; nutritional_goals_met: boolean
}

export default function Grocery() {
  const [tab, setTab] = useState<Tab>('plan')
  const [diet, setDiet] = useState<Diet>('any')
  const [days, setDays] = useState(7)
  const [mealPlan, setMealPlan] = useState<MealDay[]>([])
  const [recipes, setRecipes] = useState<Recipe[]>([])
  const [selectedRecipe, setSelectedRecipe] = useState<Recipe | null>(null)
  const [loading, setLoading] = useState(false)
  const [recipesLoading, setRecipesLoading] = useState(false)

  const generatePlan = useCallback(async () => {
    setLoading(true)
    try {
      const today = new Date().toISOString().split('T')[0]
      const prefs: Record<string, string> = {}
      if (diet !== 'any') prefs.diet = diet
      const r = await client.post('/api/grocery/meal-plan/generate', { start_date: today, days, preferences: Object.keys(prefs).length ? prefs : undefined })
      setMealPlan(r.data.meal_plans ?? [])
    } catch { setMealPlan([]) }
    finally { setLoading(false) }
  }, [diet, days])

  const loadRecipes = useCallback(async () => {
    setRecipesLoading(true)
    try {
      const r = await client.get('/api/grocery/recipes')
      setRecipes(r.data.recipes ?? [])
    } catch { setRecipes([]) }
    finally { setRecipesLoading(false) }
  }, [])

  useEffect(() => { if (tab === 'recipes' && recipes.length === 0) loadRecipes() }, [tab, loadRecipes, recipes.length])

  const viewRecipe = async (recipeId: string | null) => {
    if (!recipeId) return
    const id = recipeId.replace('/recipes/', '')
    try {
      const r = await client.get(`/api/grocery/recipes/${id}`)
      setSelectedRecipe(r.data.recipe)
    } catch {
      const found = recipes.find(r => r.recipe_id === id)
      if (found) setSelectedRecipe(found)
    }
  }

  const dayLabel = (dateStr: string) => {
    const d = new Date(dateStr + 'T12:00:00')
    return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
  }

  const TABS: { id: Tab; label: string; icon: any }[] = [
    { id: 'plan', label: 'Meal Plan', icon: Calendar },
    { id: 'recipes', label: 'Browse Recipes', icon: ChefHat },
  ]

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-11 h-11 bg-gradient-to-br from-orange-500 to-red-600 rounded-xl flex items-center justify-center">
          <UtensilsCrossed className="text-white" size={22} />
        </div>
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>Meals & Recipes</h1>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Plan meals, discover recipes, generate shopping lists</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 rounded-xl" style={{ background: 'var(--bg-tertiary)' }}>
        {TABS.map(t => {
          const Icon = t.icon
          return (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${tab === t.id ? 'shadow-sm' : ''}`}
              style={{ background: tab === t.id ? 'var(--card-bg, var(--bg-secondary))' : 'transparent', color: tab === t.id ? 'var(--text-primary)' : 'var(--text-muted)' }}>
              <Icon size={16} /> {t.label}
            </button>
          )
        })}
      </div>

      {/* ═══ Meal Plan Tab ═══ */}
      {tab === 'plan' && (
        <div className="space-y-5">
          {/* Controls */}
          <div className="rounded-2xl p-5" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}>
            <div className="flex flex-wrap items-end gap-4">
              <div>
                <label className="text-xs font-medium block mb-1" style={{ color: 'var(--text-muted)' }}>Diet</label>
                <select value={diet} onChange={e => setDiet(e.target.value as Diet)} className="px-3 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)', border: '1px solid var(--border-color)' }}>
                  <option value="any">Any</option>
                  <option value="vegetarian">Vegetarian</option>
                  <option value="vegan">Vegan</option>
                </select>
              </div>
              <div>
                <label className="text-xs font-medium block mb-1" style={{ color: 'var(--text-muted)' }}>Days</label>
                <select value={days} onChange={e => setDays(Number(e.target.value))} className="px-3 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)', border: '1px solid var(--border-color)' }}>
                  {[3, 5, 7].map(d => <option key={d} value={d}>{d} days</option>)}
                </select>
              </div>
              <button onClick={generatePlan} disabled={loading}
                className="flex items-center gap-2 px-5 py-2 rounded-xl text-sm font-semibold text-white bg-gradient-to-r from-orange-500 to-red-600 hover:shadow-lg transition-all disabled:opacity-50">
                {loading ? <RefreshCw size={16} className="animate-spin" /> : <Calendar size={16} />}
                {mealPlan.length > 0 ? 'Regenerate' : 'Generate Plan'}
              </button>
            </div>
          </div>

          {/* Plan Grid */}
          {loading && <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-500" /></div>}

          {!loading && mealPlan.length === 0 && (
            <div className="rounded-2xl p-10 text-center" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}>
              <Calendar size={40} className="mx-auto mb-3" style={{ color: 'var(--text-muted)' }} />
              <p className="font-medium" style={{ color: 'var(--text-primary)' }}>No meal plan yet</p>
              <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>Choose your preferences and hit Generate Plan to get started.</p>
            </div>
          )}

          {!loading && mealPlan.length > 0 && (
            <div className="space-y-3">
              {mealPlan.map((day, i) => (
                <div key={i} className="rounded-2xl p-4" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}>
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>{dayLabel(day.date)}</h3>
                    <div className="flex items-center gap-2">
                      <Flame size={14} style={{ color: day.nutritional_goals_met ? '#10b981' : '#f59e0b' }} />
                      <span className="text-xs font-medium" style={{ color: day.nutritional_goals_met ? '#10b981' : '#f59e0b' }}>{day.total_calories} cal</span>
                    </div>
                  </div>
                  <div className="grid sm:grid-cols-3 gap-3">
                    {([
                      { label: 'Breakfast', name: day.breakfast, cal: day.breakfast_calories, url: day.breakfast_recipe_url },
                      { label: 'Lunch', name: day.lunch, cal: day.lunch_calories, url: day.lunch_recipe_url },
                      { label: 'Dinner', name: day.dinner, cal: day.dinner_calories, url: day.dinner_recipe_url },
                    ]).map(meal => (
                      <button key={meal.label} onClick={() => viewRecipe(meal.url)} className="rounded-xl p-3 text-left transition-all hover:shadow-sm" style={{ background: 'var(--bg-tertiary)' }}>
                        <p className="text-[10px] uppercase tracking-wide font-semibold mb-1" style={{ color: 'var(--text-muted)' }}>{meal.label}</p>
                        <p className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>{meal.name || '—'}</p>
                        {meal.cal && <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>{meal.cal} cal</p>}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
              {/* Shopping List CTA */}
              <button onClick={() => { window.location.hash = 'shopping' }} className="w-full flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-semibold transition-all hover:shadow-md" style={{ background: '#10b98120', color: '#059669' }}>
                <ShoppingCart size={16} /> Generate Shopping List from Plan
              </button>
            </div>
          )}
        </div>
      )}

      {/* ═══ Browse Recipes Tab ═══ */}
      {tab === 'recipes' && (
        <div>
          {recipesLoading ? (
            <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-500" /></div>
          ) : (
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {recipes.map(r => (
                <button key={r.recipe_id} onClick={() => setSelectedRecipe(r)} className="rounded-2xl p-4 text-left transition-all hover:shadow-md" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}>
                  <h3 className="font-semibold text-sm mb-1" style={{ color: 'var(--text-primary)' }}>{r.name}</h3>
                  <p className="text-xs mb-3 line-clamp-2" style={{ color: 'var(--text-muted)' }}>{r.description}</p>
                  <div className="flex items-center gap-3 text-xs" style={{ color: 'var(--text-secondary)' }}>
                    <span className="flex items-center gap-1"><Clock size={12} /> {r.prep_time_minutes + r.cook_time_minutes}m</span>
                    <span className="flex items-center gap-1"><Flame size={12} /> {r.calories_per_serving} cal</span>
                    <span className="flex items-center gap-1"><Dumbbell size={12} /> {r.protein_grams}g</span>
                  </div>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {r.dietary_tags.filter(t => !['breakfast', 'lunch', 'dinner', 'snack'].includes(t)).slice(0, 3).map(tag => (
                      <span key={tag} className="px-2 py-0.5 rounded-full text-[10px] font-medium" style={{ background: tag === 'vegetarian' || tag === 'vegan' ? '#10b98120' : tag === 'indian' ? '#f59e0b20' : 'var(--bg-tertiary)', color: tag === 'vegetarian' || tag === 'vegan' ? '#059669' : tag === 'indian' ? '#b45309' : 'var(--text-muted)' }}>{tag}</span>
                    ))}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ═══ Recipe Detail Modal ═══ */}
      {selectedRecipe && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setSelectedRecipe(null)}>
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
          <div className="relative w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-2xl shadow-2xl" style={{ background: 'var(--bg-secondary)' }} onClick={e => e.stopPropagation()}>
            <div className="sticky top-0 flex items-center justify-between p-5 pb-3 z-10" style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-color)' }}>
              <h2 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>{selectedRecipe.name}</h2>
              <button onClick={() => setSelectedRecipe(null)} className="p-2 rounded-xl" style={{ background: 'var(--bg-tertiary)' }}><X size={18} /></button>
            </div>
            <div className="p-5 space-y-5">
              <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{selectedRecipe.description}</p>

              {/* Quick stats */}
              <div className="grid grid-cols-4 gap-3">
                {[
                  { label: 'Time', value: `${selectedRecipe.prep_time_minutes + selectedRecipe.cook_time_minutes} min`, icon: Clock },
                  { label: 'Calories', value: `${selectedRecipe.calories_per_serving}`, icon: Flame },
                  { label: 'Protein', value: `${selectedRecipe.protein_grams}g`, icon: Dumbbell },
                  { label: 'Servings', value: `${selectedRecipe.servings}`, icon: UtensilsCrossed },
                ].map(s => (
                  <div key={s.label} className="rounded-xl p-3 text-center" style={{ background: 'var(--bg-tertiary)' }}>
                    <s.icon size={16} className="mx-auto mb-1" style={{ color: 'var(--accent-primary)' }} />
                    <p className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>{s.value}</p>
                    <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>{s.label}</p>
                  </div>
                ))}
              </div>

              {/* Macros bar */}
              <div className="rounded-xl p-3" style={{ background: 'var(--bg-tertiary)' }}>
                <p className="text-xs font-semibold mb-2" style={{ color: 'var(--text-muted)' }}>Macros per serving</p>
                <div className="flex gap-4 text-xs">
                  <MacroBar label="Protein" grams={selectedRecipe.protein_grams} color="#3b82f6" />
                  <MacroBar label="Carbs" grams={selectedRecipe.carbs_grams} color="#f59e0b" />
                  <MacroBar label="Fat" grams={selectedRecipe.fat_grams} color="#ef4444" />
                </div>
              </div>

              {/* Ingredients */}
              <div>
                <h3 className="font-semibold mb-2 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                  <Leaf size={16} style={{ color: '#10b981' }} /> Ingredients
                </h3>
                <ul className="grid sm:grid-cols-2 gap-1.5">
                  {selectedRecipe.ingredients.map((ing, i) => (
                    <li key={i} className="flex items-center gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                      <ChevronRight size={12} style={{ color: 'var(--accent-primary)' }} />
                      {ing}
                    </li>
                  ))}
                </ul>
              </div>

              {/* Instructions */}
              <div>
                <h3 className="font-semibold mb-2 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                  <ChefHat size={16} style={{ color: '#8b5cf6' }} /> Instructions
                </h3>
                <ol className="space-y-2">
                  {selectedRecipe.instructions.map((step, i) => (
                    <li key={i} className="flex gap-3 text-sm" style={{ color: 'var(--text-secondary)' }}>
                      <span className="w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-bold text-white shrink-0" style={{ background: 'var(--accent-primary)' }}>{i + 1}</span>
                      {step}
                    </li>
                  ))}
                </ol>
              </div>

              {/* Tags */}
              <div className="flex flex-wrap gap-2">
                {selectedRecipe.dietary_tags.map(tag => (
                  <span key={tag} className="px-2.5 py-1 rounded-full text-xs font-medium" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}>{tag}</span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function MacroBar({ label, grams, color }: { label: string; grams: number; color: string }) {
  return (
    <div className="flex-1">
      <div className="flex justify-between mb-1">
        <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
        <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>{grams}g</span>
      </div>
      <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--bg-secondary)' }}>
        <div className="h-full rounded-full" style={{ width: `${Math.min(grams / 80 * 100, 100)}%`, background: color }} />
      </div>
    </div>
  )
}
