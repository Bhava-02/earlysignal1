import { createContext, useContext } from 'react'

export const RoleContext = createContext({ role: null, setRole: () => {} })
export const useRole = () => useContext(RoleContext)

// actions a viewer has marked planned/done (kept in this browser only)
export const DoneContext = createContext({ done: {}, mark: () => {} })
export const useDone = () => useContext(DoneContext)
