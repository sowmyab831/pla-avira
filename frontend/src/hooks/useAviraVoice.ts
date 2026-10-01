import { useCallback, useEffect, useRef, useState } from 'react'
import { voiceApi } from '../api/nexus'

type SR = any

const SpeechRecognitionCtor: SR | undefined =
  typeof window !== 'undefined' ? ((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition) : undefined

export const voiceSupported = !!SpeechRecognitionCtor

function pickBritishVoice(): SpeechSynthesisVoice | null {
  if (typeof window === 'undefined' || !window.speechSynthesis) return null
  const voices = window.speechSynthesis.getVoices()
  const prefer = ['Google UK English Female', 'Kate', 'Serena', 'Stephanie', 'Martha', 'Daniel', 'Google UK English Male']
  for (const name of prefer) {
    const v = voices.find(v => v.name.includes(name))
    if (v) return v
  }
  return voices.find(v => v.lang === 'en-GB') || voices.find(v => v.lang.startsWith('en')) || null
}

export function useAviraVoice() {
  const [listening, setListening] = useState(false)
  const [interim, setInterim] = useState('')
  const [speaking, setSpeaking] = useState(false)
  const [serverTts, setServerTts] = useState(false)
  const recRef = useRef<SR | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const onFinalRef = useRef<((text: string) => void) | null>(null)

  useEffect(() => {
    voiceApi.capabilities().then(c => setServerTts(!!c.server_tts)).catch(() => {})
    window.speechSynthesis?.getVoices()
  }, [])

  const stop = useCallback(() => {
    try { recRef.current?.stop() } catch { /* noop */ }
    setListening(false)
  }, [])

  const start = useCallback((onFinal: (text: string) => void) => {
    if (!SpeechRecognitionCtor) return false
    onFinalRef.current = onFinal
    const rec = new SpeechRecognitionCtor()
    rec.lang = 'en-US'
    rec.interimResults = true
    rec.continuous = false
    rec.maxAlternatives = 1
    let finalText = ''
    rec.onresult = (e: any) => {
      let inter = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript
        if (e.results[i].isFinal) finalText += t
        else inter += t
      }
      setInterim(inter || finalText)
    }
    rec.onend = () => {
      setListening(false)
      setInterim('')
      const text = finalText.trim()
      if (text) onFinalRef.current?.(text)
    }
    rec.onerror = () => { setListening(false); setInterim('') }
    recRef.current = rec
    setListening(true)
    rec.start()
    return true
  }, [])

  const speak = useCallback(async (text: string) => {
    if (!text) return
    setSpeaking(true)
    try {
      if (serverTts) {
        const blob = await voiceApi.tts(text)
        if (blob) {
          const url = URL.createObjectURL(blob)
          const audio = new Audio(url)
          audioRef.current = audio
          await new Promise<void>(resolve => {
            audio.onended = () => { URL.revokeObjectURL(url); resolve() }
            audio.onerror = () => resolve()
            audio.play().catch(() => resolve())
          })
          return
        }
      }
      if (window.speechSynthesis) {
        window.speechSynthesis.cancel()
        const u = new SpeechSynthesisUtterance(text)
        const v = pickBritishVoice()
        if (v) u.voice = v
        u.lang = v?.lang || 'en-GB'
        u.rate = 1.02
        u.pitch = 1.0
        await new Promise<void>(resolve => {
          u.onend = () => resolve()
          u.onerror = () => resolve()
          window.speechSynthesis.speak(u)
        })
      }
    } finally {
      setSpeaking(false)
    }
  }, [serverTts])

  const hush = useCallback(() => {
    window.speechSynthesis?.cancel()
    audioRef.current?.pause()
    setSpeaking(false)
  }, [])

  return { listening, interim, speaking, start, stop, speak, hush, supported: voiceSupported, serverTts }
}
