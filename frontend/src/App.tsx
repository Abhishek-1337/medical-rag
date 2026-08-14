import { BrowserRouter, Navigate, Route, Routes } from 'react-router'
import { PatientsList } from './views/PatientsList'
import { PatientDetail } from './views/PatientDetail'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<PatientsList />} />
        <Route path="/patients/:id" element={<PatientDetail />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
