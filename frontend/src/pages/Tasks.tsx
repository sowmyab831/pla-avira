import { useState, useEffect } from 'react'
import { CheckSquare, Plus, Calendar, Zap, Trash2, X } from 'lucide-react'
import config from '../config'

interface Task {
  id: string
  title: string
  description?: string
  completed: boolean
  category: 'task' | 'chore' | 'habit'
  dueDate?: string
  createdAt: string
}

export default function Tasks() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [activeTab, setActiveTab] = useState<'task' | 'chore' | 'habit'>('task')
  const [showAddModal, setShowAddModal] = useState(false)
  const [newTask, setNewTask] = useState({ title: '', description: '', dueDate: '' })
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetchTasks()
  }, [])

  const fetchTasks = async () => {
    try {
      const response = await fetch(`${config.apiBase}/api/tasks?user_id=default`)
      const data = await response.json()
      if (data.success) {
        setTasks(data.tasks || [])
      }
    } catch (error) {
      console.error('Failed to fetch tasks:', error)
    }
  }

  const addTask = async () => {
    if (!newTask.title.trim()) return
    
    setLoading(true)
    try {
      const response = await fetch(`${config.apiBase}/api/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'default',
          title: newTask.title,
          description: newTask.description,
          category: activeTab,
          due_date: newTask.dueDate || null
        })
      })
      const data = await response.json()
      if (data.success) {
        await fetchTasks()
        setShowAddModal(false)
        setNewTask({ title: '', description: '', dueDate: '' })
      }
    } catch (error) {
      console.error('Failed to add task:', error)
    } finally {
      setLoading(false)
    }
  }

  const toggleTask = async (taskId: string, completed: boolean) => {
    try {
      await fetch(`${config.apiBase}/api/tasks/${taskId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ completed: !completed })
      })
      await fetchTasks()
    } catch (error) {
      console.error('Failed to toggle task:', error)
    }
  }

  const deleteTask = async (taskId: string) => {
    try {
      await fetch(`${config.apiBase}/api/tasks/${taskId}`, { method: 'DELETE' })
      await fetchTasks()
    } catch (error) {
      console.error('Failed to delete task:', error)
    }
  }

  const filteredTasks = tasks.filter(t => t.category === activeTab)
  const completedCount = filteredTasks.filter(t => t.completed).length
  const habitStreak = tasks.filter(t => t.category === 'habit' && t.completed).length

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl flex items-center justify-center">
              <CheckSquare className="text-white" size={24} />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Tasks & Habits</h1>
              <p className="text-gray-600">Manage your daily life efficiently</p>
            </div>
          </div>
          <button 
            onClick={() => setShowAddModal(true)}
            className="bg-gradient-to-r from-indigo-500 to-purple-600 text-white px-6 py-3 rounded-lg font-semibold hover:shadow-lg transition-shadow flex items-center gap-2"
          >
            <Plus size={20} />
            Add {activeTab.charAt(0).toUpperCase() + activeTab.slice(1)}
          </button>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid md:grid-cols-4 gap-6 mb-8">
        <div className="bg-white p-6 rounded-xl border border-gray-200">
          <p className="text-sm text-gray-600 mb-1">Total Tasks</p>
          <p className="text-3xl font-bold">{filteredTasks.length}</p>
        </div>

        <div className="bg-white p-6 rounded-xl border border-gray-200">
          <p className="text-sm text-gray-600 mb-1">Completed</p>
          <p className="text-3xl font-bold text-green-600">{completedCount}</p>
        </div>

        <div className="bg-white p-6 rounded-xl border border-gray-200">
          <p className="text-sm text-gray-600 mb-1">All Habits</p>
          <p className="text-3xl font-bold">{tasks.filter(t => t.category === 'habit').length}</p>
        </div>

        <div className="bg-white p-6 rounded-xl border border-gray-200">
          <p className="text-sm text-gray-600 mb-1">Streak</p>
          <p className="text-3xl font-bold text-orange-600">{habitStreak} 🔥</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-8">
        <div className="flex gap-4 border-b border-gray-200 mb-6">
          <button 
            onClick={() => setActiveTab('task')}
            className={`pb-3 px-4 border-b-2 font-medium ${
              activeTab === 'task' 
                ? 'border-indigo-600 text-indigo-600' 
                : 'border-transparent text-gray-600 hover:text-gray-900'
            }`}
          >
            Tasks
          </button>
          <button 
            onClick={() => setActiveTab('chore')}
            className={`pb-3 px-4 border-b-2 font-medium ${
              activeTab === 'chore' 
                ? 'border-indigo-600 text-indigo-600' 
                : 'border-transparent text-gray-600 hover:text-gray-900'
            }`}
          >
            Chores
          </button>
          <button 
            onClick={() => setActiveTab('habit')}
            className={`pb-3 px-4 border-b-2 font-medium ${
              activeTab === 'habit' 
                ? 'border-indigo-600 text-indigo-600' 
                : 'border-transparent text-gray-600 hover:text-gray-900'
            }`}
          >
            Habits
          </button>
        </div>

        {/* Task List */}
        {filteredTasks.length === 0 ? (
          <div className="text-center py-12">
            <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <CheckSquare className="text-gray-400" size={32} />
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">No {activeTab}s yet</h3>
            <p className="text-gray-600 mb-6">Create your first {activeTab} to get started</p>
            <button 
              onClick={() => setShowAddModal(true)}
              className="bg-indigo-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-indigo-700 transition-colors"
            >
              Create {activeTab.charAt(0).toUpperCase() + activeTab.slice(1)}
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredTasks.map(task => (
              <div key={task.id} className="flex items-center gap-3 p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
                <input
                  type="checkbox"
                  checked={task.completed}
                  onChange={() => toggleTask(task.id, task.completed)}
                  className="w-5 h-5 text-indigo-600 rounded focus:ring-indigo-500"
                />
                <div className="flex-1">
                  <h4 className={`font-medium ${
                    task.completed ? 'line-through text-gray-500' : 'text-gray-900'
                  }`}>
                    {task.title}
                  </h4>
                  {task.description && (
                    <p className="text-sm text-gray-600">{task.description}</p>
                  )}
                  {task.dueDate && (
                    <p className="text-xs text-gray-500 mt-1">
                      Due: {new Date(task.dueDate).toLocaleDateString()}
                    </p>
                  )}
                </div>
                <button
                  onClick={() => deleteTask(task.id)}
                  className="text-red-600 hover:text-red-700 p-2"
                >
                  <Trash2 size={18} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Features */}
      <div className="grid md:grid-cols-3 gap-6">
        <div className="bg-white p-6 rounded-xl border border-gray-200">
          <Calendar className="text-blue-600 mb-3" size={32} />
          <h3 className="font-semibold mb-2">Weekly Planning</h3>
          <p className="text-sm text-gray-600">Organize your week ahead</p>
        </div>

        <div className="bg-white p-6 rounded-xl border border-gray-200">
          <Zap className="text-yellow-600 mb-3" size={32} />
          <h3 className="font-semibold mb-2">Habit Streaks</h3>
          <p className="text-sm text-gray-600">Build lasting habits</p>
        </div>

        <div className="bg-white p-6 rounded-xl border border-gray-200">
          <CheckSquare className="text-green-600 mb-3" size={32} />
          <h3 className="font-semibold mb-2">Smart Reminders</h3>
          <p className="text-sm text-gray-600">Never miss a task</p>
        </div>
      </div>

      {/* Add Task Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold">Add {activeTab.charAt(0).toUpperCase() + activeTab.slice(1)}</h2>
              <button onClick={() => setShowAddModal(false)} className="text-gray-500 hover:text-gray-700">
                <X size={24} />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
                <input
                  type="text"
                  value={newTask.title}
                  onChange={(e) => setNewTask({ ...newTask, title: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="Enter title"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description (optional)</label>
                <textarea
                  value={newTask.description}
                  onChange={(e) => setNewTask({ ...newTask, description: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  rows={3}
                  placeholder="Enter description"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Due Date (optional)</label>
                <input
                  type="date"
                  value={newTask.dueDate}
                  onChange={(e) => setNewTask({ ...newTask, dueDate: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div className="flex gap-3">
                <button
                  onClick={() => setShowAddModal(false)}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={addTask}
                  disabled={loading || !newTask.title.trim()}
                  className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed"
                >
                  {loading ? 'Adding...' : 'Add'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
