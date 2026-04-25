import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../store/AuthContext.jsx'
import api from '../services/api.js'

export default function AuthCallback() {
  const { login } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const token = params.get('token')

    if (!token) {
      navigate('/login?error=auth_failed')
      return
    }

    // Store token and fetch user
    localStorage.setItem('poca_token', token)

    api.get('/users/me')
      .then((res) => {
        login(token, res.data)
        navigate('/', { replace: true })
      })
      .catch(() => {
        localStorage.removeItem('poca_token')
        navigate('/login?error=auth_failed')
      })
  }, [login, navigate])

  return (
    <div className="loading-screen">
      <div className="spinner" />
      <p>Signing you in…</p>
    </div>
  )
}
