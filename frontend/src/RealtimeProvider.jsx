import { useEffect, useState } from 'react'
import { RealtimeContext, createConnection } from './realtime'

// One socket per tab while a user is signed in. Render with key={user.id} so a
// different account gets a new socket; unmounting (sign-out) disconnects it.
// A connection opens nothing until start(), so StrictMode's discarded
// initializer call leaves no socket behind.
export default function RealtimeProvider({ children }) {
  const [connection] = useState(createConnection)
  useEffect(() => connection.start(), [connection])
  return (
    <RealtimeContext.Provider value={connection}>
      {children}
    </RealtimeContext.Provider>
  )
}
