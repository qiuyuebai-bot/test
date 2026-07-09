import { useState, useCallback } from 'react'

export interface LogEntry {
  id: number
  agent: string
  content: string
  timestamp: string
  type: string
}

export function useTaskLogs() {
  const [logs, setLogs] = useState<LogEntry[]>([])

  const addLog = useCallback((agent: string, content: string, type: string = 'info') => {
    setLogs(prev => {
      const newLog: LogEntry = {
        id: Date.now() + Math.random(),
        agent,
        content,
        timestamp: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
        type,
      }
      const exists = prev.some(l => l.content === content && Date.now() - Math.floor(l.id) < 6000)
      if (exists) return prev
      return [...prev.slice(-80), newLog]
    })
  }, [])

  const clearLogs = useCallback(() => setLogs([]), [])

  return { logs, addLog, clearLogs }
}
