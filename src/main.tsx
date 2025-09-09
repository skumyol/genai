import React from 'react'
import ReactDOM from 'react-dom/client'
import App from '../App.medievalgame'
import { AdminMonitor } from './components/admin/AdminMonitor'
import medievalTheme from './theme/medievalTheme'
import { ThemeProvider, CssBaseline } from '@mui/material'
import createCache from '@emotion/cache'
import { CacheProvider } from '@emotion/react'
import '../index.css'

const createEmotionCache = () => createCache({ key: 'mui', prepend: true })

const Root: React.FC = () => {
  const isAdmin = typeof window !== 'undefined' && window.location.hash.toLowerCase().includes('admin')
  if (isAdmin) {
    return (
      <CacheProvider value={createEmotionCache()}>
        <ThemeProvider theme={medievalTheme}>
          <CssBaseline />
          <AdminMonitor />
        </ThemeProvider>
      </CacheProvider>
    )
  }
  return <App />
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
)
