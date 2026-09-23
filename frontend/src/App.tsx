import { Route, Routes } from 'react-router-dom'
import { AppShell } from '@/components/AppShell'
import { AuditPage } from '@/pages/AuditPage'
import { BenchmarkPage } from '@/pages/BenchmarkPage'
import { DemoScenariosPage } from '@/pages/DemoScenariosPage'
import { ManagerApprovalPage } from '@/pages/ManagerApprovalPage'
import { OverviewPage } from '@/pages/OverviewPage'
import { SalesCopilotPage } from '@/pages/SalesCopilotPage'

function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<OverviewPage />} />
        <Route path="/sales" element={<SalesCopilotPage />} />
        <Route path="/manager" element={<ManagerApprovalPage />} />
        <Route path="/audit" element={<AuditPage />} />
        <Route path="/benchmark" element={<BenchmarkPage />} />
        <Route path="/demo" element={<DemoScenariosPage />} />
      </Routes>
    </AppShell>
  )
}

export default App
