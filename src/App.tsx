import React from 'react';
import { TelemetryProvider, useTelemetry } from './context/TelemetryContext';
import { PreferencesProvider } from './context/PreferencesContext';
import { Header } from './components/layout/Header';
import { FooterNav } from './components/layout/FooterNav';
import { AuroraBackground } from './components/layout/AuroraBackground';
import { DashboardLayout } from './components/dashboard/DashboardLayout';
import { AnatomyPage } from './components/anatomy/AnatomyPage';
import { TestsHubPage } from './components/tests/TestsHubPage';
import { VisionTestPage } from './components/tests/VisionTestPage';
import { CognitiveTestPage } from './components/tests/CognitiveTestPage';
import { ReportsPage } from './components/reports/ReportsPage';
import { SettingsPage } from './components/settings/SettingsPage';
import { BehaviorPage } from './features/behavior/BehaviorPage';
import { ActionPlanModal } from './components/dashboard/ActionPlanModal';
import { EmergencyAlarm } from './components/emergency/EmergencyAlarm';
import { AnatomyDetailsModal } from './components/anatomy/AnatomyDetailsModal';

const AppContent: React.FC = () => {
  const { currentTab, selectedAnatomyZone, setSelectedAnatomyZone } = useTelemetry();

  const renderCurrentView = () => {
    switch (currentTab) {
      case 'dashboard':
        return <DashboardLayout />;
      case 'anatomy':
        return <AnatomyPage />;
      case 'tests':
        return <TestsHubPage />;
      case 'vision-test':
        return <VisionTestPage />;
      case 'cognitive-test':
        return <CognitiveTestPage />;
      case 'behavior':
        return <BehaviorPage />;
      case 'reports':
        return <ReportsPage />;
      case 'settings':
        return <SettingsPage />;
      default:
        return <DashboardLayout />;
    }
  };

  return (
    <div className="min-h-screen flex flex-col text-slate-800 lg:pl-[17rem]">
      <AuroraBackground />

      {/* Sol menü (masaüstü) / üst çubuk (mobil) */}
      <Header />

      <main className="flex-1 w-full max-w-[90rem] mx-auto px-4 sm:px-6 lg:px-6 py-6">
        {renderCurrentView()}
      </main>

      {/* Global Modals */}
      <ActionPlanModal />
      <EmergencyAlarm />
      <AnatomyDetailsModal
        zone={selectedAnatomyZone}
        onClose={() => setSelectedAnatomyZone(null)}
      />

      {/* Floating / Sticky Footer Dock Menu */}
      <FooterNav />
    </div>
  );
};

export function App() {
  return (
    <PreferencesProvider>
      <TelemetryProvider>
        <AppContent />
      </TelemetryProvider>
    </PreferencesProvider>
  );
}

export default App;
