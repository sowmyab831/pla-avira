import React, { useState, useEffect } from 'react'
import { Calendar as CalendarIcon, Plus, RefreshCw, AlertCircle, Upload, CheckCircle, List, Grid, ChevronLeft, ChevronRight } from 'lucide-react'
import config from '../config'

interface CalendarEvent {
  id?: string
  date: string
  time?: string
  title: string
  type: string
  description?: string
  source?: string
  priority?: string
  is_actionable?: boolean
}

export default function Calendar() {
  const [events, setEvents] = useState<CalendarEvent[]>([])
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [showAddEvent, setShowAddEvent] = useState(false)
  const [showAddActionable, setShowAddActionable] = useState(false)
  const [showUploadPDF, setShowUploadPDF] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [viewMode, setViewMode] = useState<'list' | 'calendar'>('list')
  const [currentMonth, setCurrentMonth] = useState(new Date())
  const [newEvent, setNewEvent] = useState({
    date: new Date().toISOString().split('T')[0],
    title: '',
    time: '',
    type: 'custom',
    description: ''
  })
  const [newActionable, setNewActionable] = useState({
    date: new Date().toISOString().split('T')[0],
    time: '',
    title: '',
    description: '',
    priority: 'medium'
  })

  // Fetch events on mount
  useEffect(() => {
    fetchEvents()
  }, [])

  const fetchEvents = async () => {
    try {
      setLoading(true)
      const response = await fetch(`${config.endpoints.calendarUpcoming}?days=90`)
      const data = await response.json()
      if (data.success) {
        setEvents(data.events)
      }
    } catch (error) {
      console.error('Failed to fetch events:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleAddEvent = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const params = new URLSearchParams({
        date: newEvent.date,
        title: newEvent.title,
        event_type: newEvent.type,
        description: newEvent.description,
        ...(newEvent.time && { time: newEvent.time })
      })
      const response = await fetch(`${config.endpoints.calendarEvents}?${params}`, {
        method: 'POST'
      })
      const data = await response.json()
      if (data.success) {
        setEvents([...events, data.event])
        setNewEvent({
          date: new Date().toISOString().split('T')[0],
          title: '',
          time: '',
          type: 'custom',
          description: ''
        })
        setShowAddEvent(false)
      }
    } catch (error) {
      console.error('Failed to add event:', error)
      alert('Failed to add event')
    }
  }

  const handleSyncSchools = async () => {
    try {
      setSyncing(true)
      const response = await fetch(config.endpoints.calendarSyncAllSchools, {
        method: 'POST'
      })
      const data = await response.json()
      if (data.success) {
        alert(`Synced ${data.total_events_synced} events from school calendars`)
        fetchEvents()
      }
    } catch (error) {
      console.error('Failed to sync schools:', error)
      alert('Failed to sync school calendars')
    } finally {
      setSyncing(false)
    }
  }

  const handleUploadFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    try {
      setUploading(true)
      const formData = new FormData()
      formData.append('file', file)

      // Determine endpoint based on file type
      const isCsv = file.name.toLowerCase().endsWith('.csv')
      const endpoint = isCsv ? config.endpoints.calendarUploadCsv : config.endpoints.calendarUploadPdf

      const response = await fetch(endpoint, {
        method: 'POST',
        body: formData
      })
      
      if (!response.ok) {
        const errData = await response.json()
        throw new Error(errData.detail || 'Upload failed')
      }
      
      const data = await response.json()
      if (data.success) {
        alert(`Imported ${data.events_extracted} events from ${file.name}`)
        fetchEvents()
        setShowUploadPDF(false)
      }
    } catch (error: any) {
      console.error('Failed to upload file:', error)
      alert(`Failed to upload: ${error.message || 'Unknown error'}`)
    } finally {
      setUploading(false)
    }
  }

  const handleAddActionable = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const params = new URLSearchParams({
        date: newActionable.date,
        title: newActionable.title,
        description: newActionable.description,
        priority: newActionable.priority,
        ...(newActionable.time && { time: newActionable.time })
      })

      const response = await fetch(`${config.endpoints.calendarActionableItem}?${params}`, {
        method: 'POST'
      })
      const data = await response.json()
      if (data.success) {
        setEvents([...events, data.event])
        setNewActionable({
          date: new Date().toISOString().split('T')[0],
          time: '',
          title: '',
          description: '',
          priority: 'medium'
        })
        setShowAddActionable(false)
        alert('Actionable item added!')
      }
    } catch (error) {
      console.error('Failed to add actionable item:', error)
      alert('Failed to add actionable item')
    }
  }

  const getEventColor = (type: string) => {
    const colors: Record<string, string> = {
      holiday: 'bg-red-100 border-red-300 text-red-900',
      break: 'bg-orange-100 border-orange-300 text-orange-900',
      appointment: 'bg-blue-100 border-blue-300 text-blue-900',
      assignment_due: 'bg-yellow-100 border-yellow-300 text-yellow-900',
      test: 'bg-purple-100 border-purple-300 text-purple-900',
      custom: 'bg-green-100 border-green-300 text-green-900',
      school_day: 'bg-gray-100 border-gray-300 text-gray-900'
    }
    return colors[type] || colors.custom
  }

  const groupedEvents = events.reduce((acc, event) => {
    const date = event.date
    if (!acc[date]) acc[date] = []
    acc[date].push(event)
    return acc
  }, {} as Record<string, CalendarEvent[]>)

  const sortedDates = Object.keys(groupedEvents).sort()

  // Calendar view helpers
  const getDaysInMonth = (date: Date) => {
    const year = date.getFullYear()
    const month = date.getMonth()
    const firstDay = new Date(year, month, 1)
    const lastDay = new Date(year, month + 1, 0)
    const daysInMonth = lastDay.getDate()
    const startingDay = firstDay.getDay()
    return { daysInMonth, startingDay, year, month }
  }

  const getEventsForDate = (date: string) => {
    return events.filter(e => e.date === date)
  }

  const { daysInMonth, startingDay, year, month } = getDaysInMonth(currentMonth)
  const monthName = currentMonth.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })

  const navigateMonth = (direction: 'prev' | 'next') => {
    setCurrentMonth(prev => {
      const newDate = new Date(prev)
      newDate.setMonth(newDate.getMonth() + (direction === 'next' ? 1 : -1))
      return newDate
    })
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Calendar</h1>
          <p className="text-gray-600 mt-2">Manage school calendars, holidays, and appointments</p>
        </div>
        <div className="flex gap-2 flex-wrap items-center">
          {/* View Toggle */}
          <div className="flex bg-gray-100 rounded-lg p-1 mr-2">
            <button
              onClick={() => setViewMode('list')}
              className={`px-3 py-1.5 rounded-md flex items-center gap-1 text-sm font-medium transition-colors ${
                viewMode === 'list' ? 'bg-white shadow text-blue-600' : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <List size={16} /> List
            </button>
            <button
              onClick={() => setViewMode('calendar')}
              className={`px-3 py-1.5 rounded-md flex items-center gap-1 text-sm font-medium transition-colors ${
                viewMode === 'calendar' ? 'bg-white shadow text-blue-600' : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <Grid size={16} /> Calendar
            </button>
          </div>

          <button
            onClick={handleSyncSchools}
            disabled={syncing}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            <RefreshCw size={18} className={syncing ? 'animate-spin' : ''} />
            {syncing ? 'Syncing...' : 'Sync Schools'}
          </button>
          <button
            onClick={() => setShowUploadPDF(!showUploadPDF)}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
          >
            <Upload size={18} />
            Upload PDF/CSV
          </button>
          <button
            onClick={() => setShowAddActionable(!showAddActionable)}
            className="flex items-center gap-2 px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700"
          >
            <CheckCircle size={18} />
            Add Action Item
          </button>
          <button
            onClick={() => setShowAddEvent(!showAddEvent)}
            className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
          >
            <Plus size={18} />
            Add Event
          </button>
        </div>
      </div>

      {/* Upload Calendar File Form */}
      {showUploadPDF && (
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Upload School Calendar</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Select PDF or CSV File</label>
              <input
                type="file"
                accept=".pdf,.csv"
                onChange={handleUploadFile}
                disabled={uploading}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
              <p className="text-sm text-gray-500 mt-2">Upload a school calendar PDF or CSV to import dates and events</p>
            </div>
            <div className="flex gap-4">
              <button
                type="button"
                onClick={() => setShowUploadPDF(false)}
                className="px-6 py-2 bg-gray-300 text-gray-900 rounded-lg hover:bg-gray-400"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Actionable Item Form */}
      {showAddActionable && (
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Add Actionable Item</h2>
          <form onSubmit={handleAddActionable} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Date</label>
                <input
                  type="date"
                  value={newActionable.date}
                  onChange={(e) => setNewActionable({ ...newActionable, date: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Time (optional)</label>
                <input
                  type="time"
                  value={newActionable.time}
                  onChange={(e) => setNewActionable({ ...newActionable, time: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Action Item Title</label>
              <input
                type="text"
                value={newActionable.title}
                onChange={(e) => setNewActionable({ ...newActionable, title: e.target.value })}
                placeholder="What needs to be done?"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Priority</label>
              <select
                value={newActionable.priority}
                onChange={(e) => setNewActionable({ ...newActionable, priority: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Description</label>
              <textarea
                value={newActionable.description}
                onChange={(e) => setNewActionable({ ...newActionable, description: e.target.value })}
                placeholder="Additional details"
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>

            <div className="flex gap-4">
              <button
                type="submit"
                className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
              >
                Add Action Item
              </button>
              <button
                type="button"
                onClick={() => setShowAddActionable(false)}
                className="px-6 py-2 bg-gray-300 text-gray-900 rounded-lg hover:bg-gray-400"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Add Event Form */}
      {showAddEvent && (
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Add New Event</h2>
          <form onSubmit={handleAddEvent} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Date</label>
                <input
                  type="date"
                  value={newEvent.date}
                  onChange={(e) => setNewEvent({ ...newEvent, date: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Time (optional)</label>
                <input
                  type="time"
                  value={newEvent.time}
                  onChange={(e) => setNewEvent({ ...newEvent, time: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Title</label>
              <input
                type="text"
                value={newEvent.title}
                onChange={(e) => setNewEvent({ ...newEvent, title: e.target.value })}
                placeholder="Event title"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Type</label>
              <select
                value={newEvent.type}
                onChange={(e) => setNewEvent({ ...newEvent, type: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="custom">Custom</option>
                <option value="appointment">Appointment</option>
                <option value="assignment_due">Assignment Due</option>
                <option value="test">Test</option>
                <option value="holiday">Holiday</option>
                <option value="break">Break</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Description</label>
              <textarea
                value={newEvent.description}
                onChange={(e) => setNewEvent({ ...newEvent, description: e.target.value })}
                placeholder="Event description"
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>

            <div className="flex gap-4">
              <button
                type="submit"
                className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
              >
                Add Event
              </button>
              <button
                type="button"
                onClick={() => setShowAddEvent(false)}
                className="px-6 py-2 bg-gray-300 text-gray-900 rounded-lg hover:bg-gray-400"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Events Display */}
      {loading ? (
        <div className="text-center py-12">
          <p className="text-gray-600">Loading events...</p>
        </div>
      ) : sortedDates.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <CalendarIcon className="mx-auto text-gray-400 mb-4" size={48} />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">No events yet</h2>
          <p className="text-gray-600 mb-6">Sync school calendars or add your own events to get started</p>
          <button
            onClick={handleSyncSchools}
            className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
          >
            Sync School Calendars
          </button>
        </div>
      ) : viewMode === 'calendar' ? (
        /* Calendar Grid View */
        <div className="bg-white rounded-lg shadow overflow-hidden">
          {/* Month Navigation */}
          <div className="flex items-center justify-between bg-gray-50 px-6 py-4 border-b">
            <button
              onClick={() => navigateMonth('prev')}
              className="p-2 hover:bg-gray-200 rounded-lg"
            >
              <ChevronLeft size={20} />
            </button>
            <h3 className="text-xl font-semibold text-gray-900">{monthName}</h3>
            <button
              onClick={() => navigateMonth('next')}
              className="p-2 hover:bg-gray-200 rounded-lg"
            >
              <ChevronRight size={20} />
            </button>
          </div>

          {/* Calendar Grid */}
          <div className="p-4">
            {/* Day Headers */}
            <div className="grid grid-cols-7 gap-1 mb-2">
              {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(day => (
                <div key={day} className="text-center text-sm font-medium text-gray-500 py-2">
                  {day}
                </div>
              ))}
            </div>

            {/* Calendar Days */}
            <div className="grid grid-cols-7 gap-1">
              {/* Empty cells for days before start of month */}
              {Array.from({ length: startingDay }, (_, i) => (
                <div key={`empty-${i}`} className="h-24 bg-gray-50 rounded" />
              ))}

              {/* Days of the month */}
              {Array.from({ length: daysInMonth }, (_, i) => {
                const day = i + 1
                const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
                const dayEvents = getEventsForDate(dateStr)
                const isToday = dateStr === new Date().toISOString().split('T')[0]

                return (
                  <div
                    key={day}
                    className={`h-24 p-1 border rounded overflow-hidden ${
                      isToday ? 'bg-blue-50 border-blue-300' : 'bg-white border-gray-200'
                    }`}
                  >
                    <div className={`text-sm font-medium mb-1 ${isToday ? 'text-blue-600' : 'text-gray-700'}`}>
                      {day}
                    </div>
                    <div className="space-y-0.5 overflow-y-auto max-h-16">
                      {dayEvents.slice(0, 3).map((event, idx) => (
                        <div
                          key={idx}
                          className={`text-xs px-1 py-0.5 rounded truncate ${getEventColor(event.type)}`}
                          title={event.title}
                        >
                          {event.title}
                        </div>
                      ))}
                      {dayEvents.length > 3 && (
                        <div className="text-xs text-gray-500 px-1">+{dayEvents.length - 3} more</div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      ) : (
        /* List View */
        <div className="space-y-6">
          {sortedDates.map((date) => (
            <div key={date} className="bg-white rounded-lg shadow overflow-hidden">
              <div className="bg-gray-50 px-6 py-4 border-b border-gray-200">
                <h3 className="text-lg font-semibold text-gray-900">
                  {new Date(date).toLocaleDateString('en-US', {
                    weekday: 'long',
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric'
                  })}
                </h3>
              </div>
              <div className="divide-y divide-gray-200">
                {groupedEvents[date].map((event, idx) => (
                  <div
                    key={idx}
                    className={`p-4 border-l-4 ${getEventColor(event.type)}`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <h4 className="font-semibold">{event.title}</h4>
                        {event.time && (
                          <p className="text-sm opacity-75">
                            {event.time}
                          </p>
                        )}
                        {event.description && (
                          <p className="text-sm mt-2 opacity-75">{event.description}</p>
                        )}
                        <div className="flex gap-2 mt-2">
                          <span className="text-xs px-2 py-1 bg-white bg-opacity-50 rounded">
                            {event.type.replace('_', ' ')}
                          </span>
                          {event.source && (
                            <span className="text-xs px-2 py-1 bg-white bg-opacity-50 rounded">
                              {event.source.replace('_', ' ')}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Info Box */}
      <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-6 flex gap-4">
        <AlertCircle className="text-blue-600 flex-shrink-0" size={24} />
        <div>
          <h3 className="font-semibold text-blue-900">School Calendar Sync</h3>
          <p className="text-blue-800 text-sm mt-2">
            Click "Sync Schools" to automatically pull events from Socrates Academy, LN Charter, and your family calendar.
            You can also manually add appointments and important dates.
          </p>
        </div>
      </div>
    </div>
  )
}
