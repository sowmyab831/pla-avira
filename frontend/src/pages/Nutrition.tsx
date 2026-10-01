import { useState, useEffect } from 'react'
import { Utensils, Loader2, ChefHat, Apple, Salad, Scale, Ruler, Target, Trash2, History, BookOpen, ChevronDown, ChevronUp } from 'lucide-react'
import config from '../config'

interface Meal {
  name: string
  calories: number
  protein: number
  carbs: number
  fat: number
  ingredients: string[]
  instructions?: string
  cookingSteps?: string[]
}

interface MealPlan {
  breakfast: Meal[]
  lunch: Meal[]
  dinner: Meal[]
  snacks?: Meal[]
  dailyProteinTarget?: number
  proteinDistribution?: { breakfast: number; lunch: number; dinner: number; snacks: number }
}

interface NutritionHistory {
  id: string
  date: string
  mealPlan: MealPlan
  profile: { age: string; gender: string; height: string; weight: string; activityLevel: string }
}

export default function Nutrition() {
  const [age, setAge] = useState('')
  const [gender, setGender] = useState('male')
  const [height, setHeight] = useState('')
  const [weight, setWeight] = useState('')
  const [activityLevel, setActivityLevel] = useState('moderate')
  const [dietaryPreferences, setDietaryPreferences] = useState<string[]>([])
  const [healthGoals, setHealthGoals] = useState<string[]>([])
  const [cuisinePreferences, setCuisinePreferences] = useState('')
  const [loading, setLoading] = useState(false)
  const [mealPlan, setMealPlan] = useState<MealPlan | null>(null)
  const [history, setHistory] = useState<NutritionHistory[]>([])
  const [showHistory, setShowHistory] = useState(false)
  const [expandedMeal, setExpandedMeal] = useState<string | null>(null)

  const dietOptions = ['vegetarian', 'vegan', 'gluten_free', 'dairy_free', 'low_carb', 'keto', 'high_protein', 'mediterranean']
  const goalOptions = ['weight_loss', 'muscle_gain', 'maintenance', 'energy_boost', 'heart_health', 'diabetes_friendly']
  const activityOptions = [
    { value: 'sedentary', label: 'Sedentary (little or no exercise)' },
    { value: 'light', label: 'Light (1-3 days/week)' },
    { value: 'moderate', label: 'Moderate (3-5 days/week)' },
    { value: 'active', label: 'Active (6-7 days/week)' },
    { value: 'very_active', label: 'Very Active (athlete/physical job)' }
  ]

  useEffect(() => {
    const savedHistory = localStorage.getItem('nutritionHistory')
    if (savedHistory) {
      setHistory(JSON.parse(savedHistory))
    }
  }, [])

  const calculateProteinNeeds = (): number => {
    if (!weight) return 0
    const weightKg = parseFloat(weight) * 0.453592
    let multiplier = 0.8
    if (healthGoals.includes('muscle_gain')) multiplier = 1.6
    else if (healthGoals.includes('weight_loss')) multiplier = 1.2
    else if (activityLevel === 'active' || activityLevel === 'very_active') multiplier = 1.4
    return Math.round(weightKg * multiplier)
  }

  const calculateBMI = (): number => {
    if (!height || !weight) return 0
    const heightM = parseFloat(height) * 0.0254
    const weightKg = parseFloat(weight) * 0.453592
    return Math.round((weightKg / (heightM * heightM)) * 10) / 10
  }

  const getBMICategory = (bmi: number): { label: string; color: string } => {
    if (bmi < 18.5) return { label: 'Underweight', color: 'text-yellow-600' }
    if (bmi < 25) return { label: 'Normal', color: 'text-green-600' }
    if (bmi < 30) return { label: 'Overweight', color: 'text-orange-600' }
    return { label: 'Obese', color: 'text-red-600' }
  }

  const toggleOption = (option: string, list: string[], setter: (val: string[]) => void) => {
    if (list.includes(option)) {
      setter(list.filter(o => o !== option))
    } else {
      setter([...list, option])
    }
  }

  const saveToHistory = (plan: MealPlan) => {
    const newEntry: NutritionHistory = {
      id: Date.now().toString(),
      date: new Date().toISOString(),
      mealPlan: plan,
      profile: { age, gender, height, weight, activityLevel }
    }
    const updated = [newEntry, ...history].slice(0, 10)
    setHistory(updated)
    localStorage.setItem('nutritionHistory', JSON.stringify(updated))
  }

  const clearHistory = () => {
    if (confirm('Are you sure you want to clear all meal plan history?')) {
      setHistory([])
      localStorage.removeItem('nutritionHistory')
    }
  }

  const handleGetMealPlan = async () => {
    if (!age || !height || !weight) {
      alert('Please enter your age, height, and weight')
      return
    }

    try {
      setLoading(true)
      const proteinTarget = calculateProteinNeeds()
      const response = await fetch(`${config.apiBase}/api/nutrition/meal-plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          age: parseInt(age),
          gender,
          height: parseFloat(height),
          weight: parseFloat(weight),
          activity_level: activityLevel,
          dietary_preferences: dietaryPreferences,
          health_goals: healthGoals,
          cuisine_preferences: cuisinePreferences,
          protein_target: proteinTarget,
          include_cooking_steps: true,
          allergies: []
        })
      })

      const data = await response.json()
      if (data.success && data.meal_plan) {
        const planWithProtein = {
          ...data.meal_plan,
          dailyProteinTarget: proteinTarget,
          proteinDistribution: {
            breakfast: Math.round(proteinTarget * 0.25),
            lunch: Math.round(proteinTarget * 0.35),
            dinner: Math.round(proteinTarget * 0.30),
            snacks: Math.round(proteinTarget * 0.10)
          }
        }
        setMealPlan(planWithProtein)
        saveToHistory(planWithProtein)
      } else {
        alert('Failed to generate meal plan')
      }
    } catch (error) {
      console.error('Failed to get meal plan:', error)
      alert('Failed to get meal plan')
    } finally {
      setLoading(false)
    }
  }

  const renderMealCard = (meal: Meal, index: number, mealType: string) => {
    const isExpanded = expandedMeal === `${mealType}-${index}`
    const cookingSteps = meal.cookingSteps || [
      `Prep all ingredients: ${meal.ingredients?.slice(0, 3).join(', ')}`,
      'Heat pan/oven to medium-high temperature',
      'Combine main ingredients and cook for 5-10 minutes',
      'Season to taste and plate',
      'Serve immediately and enjoy!'
    ]

    return (
      <div key={index} className="bg-white p-4 rounded-lg border border-gray-200 hover:shadow-md transition-shadow">
        <h4 className="font-semibold text-lg text-gray-900 mb-2">{meal.name}</h4>
        
        {/* Macros */}
        <div className="grid grid-cols-4 gap-2 mb-3 text-sm">
          <div className="bg-blue-50 p-2 rounded text-center">
            <p className="text-xs text-gray-600">Calories</p>
            <p className="font-bold text-blue-600">{meal.calories}</p>
          </div>
          <div className="bg-green-50 p-2 rounded text-center">
            <p className="text-xs text-gray-600">Protein</p>
            <p className="font-bold text-green-600">{meal.protein}g</p>
          </div>
          <div className="bg-yellow-50 p-2 rounded text-center">
            <p className="text-xs text-gray-600">Carbs</p>
            <p className="font-bold text-yellow-600">{meal.carbs}g</p>
          </div>
          <div className="bg-purple-50 p-2 rounded text-center">
            <p className="text-xs text-gray-600">Fat</p>
            <p className="font-bold text-purple-600">{meal.fat}g</p>
          </div>
        </div>

        {/* Ingredients */}
        {meal.ingredients && meal.ingredients.length > 0 && (
          <div className="mb-2">
            <p className="text-xs font-semibold text-gray-700 mb-1">Ingredients:</p>
            <ul className="text-xs text-gray-600 space-y-0.5">
              {meal.ingredients.slice(0, 5).map((ing, idx) => (
                <li key={idx}>• {ing}</li>
              ))}
            </ul>
          </div>
        )}

        {/* How to Cook Toggle */}
        <button 
          onClick={() => setExpandedMeal(isExpanded ? null : `${mealType}-${index}`)}
          className="w-full mt-2 pt-2 border-t border-gray-100 flex items-center justify-between text-sm text-green-600 hover:text-green-700"
        >
          <span className="flex items-center gap-1">
            <BookOpen size={14} />
            How to Cook
          </span>
          {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>

        {/* Cooking Steps */}
        {isExpanded && (
          <div className="mt-3 p-3 bg-green-50 rounded-lg">
            <p className="text-xs font-semibold text-green-800 mb-2">Quick Recipe (4-5 Steps):</p>
            <ol className="text-xs text-green-700 space-y-1">
              {cookingSteps.map((step, idx) => (
                <li key={idx} className="flex gap-2">
                  <span className="font-bold">{idx + 1}.</span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>
    )
  }

  const bmi = calculateBMI()
  const bmiCategory = getBMICategory(bmi)
  const proteinNeeds = calculateProteinNeeds()

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8 flex justify-between items-start">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-gradient-to-br from-green-500 to-emerald-600 rounded-xl flex items-center justify-center">
            <Utensils className="text-white" size={24} />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">AI Nutrition Planner</h1>
            <p className="text-gray-600">Get personalized meal plans with protein tracking</p>
          </div>
        </div>
        
        {/* History Button */}
        <div className="flex gap-2">
          <button
            onClick={() => setShowHistory(!showHistory)}
            className="flex items-center gap-2 px-4 py-2 bg-gray-100 rounded-lg hover:bg-gray-200"
          >
            <History size={18} />
            History ({history.length})
          </button>
          {history.length > 0 && (
            <button
              onClick={clearHistory}
              className="flex items-center gap-2 px-4 py-2 bg-red-100 text-red-600 rounded-lg hover:bg-red-200"
            >
              <Trash2 size={18} />
              Clear
            </button>
          )}
        </div>
      </div>

      {/* History Panel */}
      {showHistory && history.length > 0 && (
        <div className="bg-gray-50 p-6 rounded-xl border border-gray-200 mb-8">
          <h3 className="font-semibold text-lg mb-4">Meal Plan History</h3>
          <div className="space-y-3">
            {history.map((entry) => (
              <div key={entry.id} className="bg-white p-4 rounded-lg border border-gray-200 flex justify-between items-center">
                <div>
                  <p className="font-medium">{new Date(entry.date).toLocaleDateString()}</p>
                  <p className="text-sm text-gray-600">
                    Age: {entry.profile.age}, Weight: {entry.profile.weight} lbs, Height: {entry.profile.height}"
                  </p>
                </div>
                <button
                  onClick={() => setMealPlan(entry.mealPlan)}
                  className="px-4 py-2 bg-green-100 text-green-700 rounded-lg hover:bg-green-200 text-sm"
                >
                  Load Plan
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Input Form */}
      <div className="bg-white p-8 rounded-xl border border-gray-200 mb-8">
        <h2 className="text-xl font-semibold mb-6">Your Health Profile</h2>
        
        {/* Body Metrics */}
        <div className="grid md:grid-cols-4 gap-6 mb-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2 flex items-center gap-1">
              <Scale size={16} /> Weight (lbs)
            </label>
            <input
              type="number"
              value={weight}
              onChange={(e) => setWeight(e.target.value)}
              placeholder="e.g., 150"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-green-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2 flex items-center gap-1">
              <Ruler size={16} /> Height (inches)
            </label>
            <input
              type="number"
              value={height}
              onChange={(e) => setHeight(e.target.value)}
              placeholder="e.g., 68"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-green-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Age</label>
            <input
              type="number"
              value={age}
              onChange={(e) => setAge(e.target.value)}
              placeholder="Enter age"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-green-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Gender</label>
            <select
              value={gender}
              onChange={(e) => setGender(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-green-500 focus:outline-none"
            >
              <option value="male">Male</option>
              <option value="female">Female</option>
              <option value="other">Other</option>
            </select>
          </div>
        </div>

        {/* BMI & Protein Display */}
        {(height && weight) && (
          <div className="grid md:grid-cols-2 gap-4 mb-6">
            <div className="bg-gradient-to-r from-blue-50 to-cyan-50 p-4 rounded-lg border border-blue-200">
              <div className="flex items-center gap-2 mb-2">
                <Target size={20} className="text-blue-600" />
                <span className="font-semibold">Your BMI</span>
              </div>
              <p className="text-3xl font-bold text-blue-700">{bmi}</p>
              <p className={`text-sm font-medium ${bmiCategory.color}`}>{bmiCategory.label}</p>
            </div>
            
            <div className="bg-gradient-to-r from-green-50 to-emerald-50 p-4 rounded-lg border border-green-200">
              <div className="flex items-center gap-2 mb-2">
                <Apple size={20} className="text-green-600" />
                <span className="font-semibold">Daily Protein Target</span>
              </div>
              <p className="text-3xl font-bold text-green-700">{proteinNeeds}g</p>
              <p className="text-sm text-green-600">Based on your weight & goals</p>
            </div>
          </div>
        )}

        {/* Activity Level */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">Activity Level</label>
          <select
            value={activityLevel}
            onChange={(e) => setActivityLevel(e.target.value)}
            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-green-500 focus:outline-none"
          >
            {activityOptions.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>

        {/* Dietary Preferences */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">Dietary Preferences</label>
          <div className="flex flex-wrap gap-2">
            {dietOptions.map(option => (
              <button
                key={option}
                onClick={() => toggleOption(option, dietaryPreferences, setDietaryPreferences)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  dietaryPreferences.includes(option)
                    ? 'bg-green-500 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {option.replace(/_/g, ' ')}
              </button>
            ))}
          </div>
        </div>

        {/* Cuisine Preferences */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Cuisine Preferences
            <span className="text-xs text-gray-500 ml-2">(e.g., Indian, Telugu, Asian, Italian, Mediterranean)</span>
          </label>
          <input
            type="text"
            value={cuisinePreferences}
            onChange={(e) => setCuisinePreferences(e.target.value)}
            placeholder="Enter your preferred cuisines..."
            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-green-500 focus:outline-none"
          />
        </div>

        {/* Health Goals */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">Health Goals</label>
          <div className="flex flex-wrap gap-2">
            {goalOptions.map(goal => (
              <button
                key={goal}
                onClick={() => toggleOption(goal, healthGoals, setHealthGoals)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  healthGoals.includes(goal)
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {goal.replace(/_/g, ' ')}
              </button>
            ))}
          </div>
        </div>

        {/* Generate Button */}
        <button
          onClick={handleGetMealPlan}
          disabled={loading}
          className="w-full bg-gradient-to-r from-green-500 to-emerald-600 text-white py-4 rounded-lg font-semibold hover:shadow-lg transition-shadow disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <Loader2 className="animate-spin" size={20} />
              Generating Personalized Meal Plan...
            </>
          ) : (
            <>
              <ChefHat size={20} />
              Generate Meal Plan with Protein Distribution
            </>
          )}
        </button>
      </div>

      {/* Protein Distribution Summary */}
      {mealPlan && mealPlan.dailyProteinTarget && (
        <div className="bg-gradient-to-r from-green-100 to-emerald-100 p-6 rounded-xl border border-green-300 mb-8">
          <h3 className="font-bold text-lg text-green-900 mb-4 flex items-center gap-2">
            <Target size={20} /> Daily Protein Distribution ({mealPlan.dailyProteinTarget}g total)
          </h3>
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-white p-4 rounded-lg text-center">
              <p className="text-sm text-gray-600">Breakfast</p>
              <p className="text-2xl font-bold text-yellow-600">{mealPlan.proteinDistribution?.breakfast}g</p>
              <p className="text-xs text-gray-500">25% of daily</p>
            </div>
            <div className="bg-white p-4 rounded-lg text-center">
              <p className="text-sm text-gray-600">Lunch</p>
              <p className="text-2xl font-bold text-green-600">{mealPlan.proteinDistribution?.lunch}g</p>
              <p className="text-xs text-gray-500">35% of daily</p>
            </div>
            <div className="bg-white p-4 rounded-lg text-center">
              <p className="text-sm text-gray-600">Dinner</p>
              <p className="text-2xl font-bold text-blue-600">{mealPlan.proteinDistribution?.dinner}g</p>
              <p className="text-xs text-gray-500">30% of daily</p>
            </div>
            <div className="bg-white p-4 rounded-lg text-center">
              <p className="text-sm text-gray-600">Snacks</p>
              <p className="text-2xl font-bold text-purple-600">{mealPlan.proteinDistribution?.snacks}g</p>
              <p className="text-xs text-gray-500">10% of daily</p>
            </div>
          </div>
        </div>
      )}

      {/* Meal Plan Results */}
      {mealPlan && (
        <div className="space-y-8">
          {/* Breakfast */}
          <div className="bg-gradient-to-br from-yellow-50 to-orange-50 p-6 rounded-xl border border-yellow-200">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Apple className="text-yellow-600" size={24} />
                <h3 className="text-2xl font-bold text-gray-900">Breakfast Options</h3>
              </div>
              <span className="bg-yellow-200 text-yellow-800 px-3 py-1 rounded-full text-sm font-medium">
                Target: {mealPlan.proteinDistribution?.breakfast}g protein
              </span>
            </div>
            <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
              {mealPlan.breakfast.map((meal, idx) => renderMealCard(meal, idx, 'breakfast'))}
            </div>
          </div>

          {/* Lunch */}
          <div className="bg-gradient-to-br from-green-50 to-emerald-50 p-6 rounded-xl border border-green-200">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Salad className="text-green-600" size={24} />
                <h3 className="text-2xl font-bold text-gray-900">Lunch Options</h3>
              </div>
              <span className="bg-green-200 text-green-800 px-3 py-1 rounded-full text-sm font-medium">
                Target: {mealPlan.proteinDistribution?.lunch}g protein
              </span>
            </div>
            <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
              {mealPlan.lunch.map((meal, idx) => renderMealCard(meal, idx, 'lunch'))}
            </div>
          </div>

          {/* Dinner */}
          <div className="bg-gradient-to-br from-blue-50 to-indigo-50 p-6 rounded-xl border border-blue-200">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Utensils className="text-blue-600" size={24} />
                <h3 className="text-2xl font-bold text-gray-900">Dinner Options</h3>
              </div>
              <span className="bg-blue-200 text-blue-800 px-3 py-1 rounded-full text-sm font-medium">
                Target: {mealPlan.proteinDistribution?.dinner}g protein
              </span>
            </div>
            <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
              {mealPlan.dinner.map((meal, idx) => renderMealCard(meal, idx, 'dinner'))}
            </div>
          </div>

          {/* Snacks (if available) */}
          {mealPlan.snacks && mealPlan.snacks.length > 0 && (
            <div className="bg-gradient-to-br from-purple-50 to-pink-50 p-6 rounded-xl border border-purple-200">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <ChefHat className="text-purple-600" size={24} />
                  <h3 className="text-2xl font-bold text-gray-900">Snack Options</h3>
                </div>
                <span className="bg-purple-200 text-purple-800 px-3 py-1 rounded-full text-sm font-medium">
                  Target: {mealPlan.proteinDistribution?.snacks}g protein
                </span>
              </div>
              <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
                {mealPlan.snacks.map((meal, idx) => renderMealCard(meal, idx, 'snacks'))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Empty State */}
      {!mealPlan && !loading && (
        <div className="bg-gray-50 p-12 rounded-xl border border-gray-200 text-center">
          <ChefHat className="mx-auto text-gray-400 mb-4" size={48} />
          <h3 className="text-xl font-semibold text-gray-700 mb-2">No Meal Plan Yet</h3>
          <p className="text-gray-600">Enter your height, weight, and other details above to get a personalized meal plan with protein tracking!</p>
        </div>
      )}
    </div>
  )
}
