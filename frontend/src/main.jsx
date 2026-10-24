import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { hasData, setData } from './lib/data'
import { boot } from './lib/server'
import './styles.css'

const root = ReactDOM.createRoot(document.getElementById('root'))

boot().then((latest) => {
  if (latest && latest.meta) setData(latest)
  if (!hasData()) {
    root.render(
      <div className="boot"><div><b>EarlySignal could not load its data.</b><p>The server may still be preparing it. Wait a minute and refresh the page.</p></div></div>,
    )
    return
  }
  root.render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  )
})
