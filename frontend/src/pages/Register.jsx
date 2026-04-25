// Register redirects to Login — sign-up and sign-in are the same flow
import { Navigate } from 'react-router-dom'
export default function Register() {
  return <Navigate to="/login" replace />
}
