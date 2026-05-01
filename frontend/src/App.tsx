import React, { ReactNode } from 'react';
import { BrowserRouter, Routes, Route, Outlet, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from '@/contexts/ThemeContext';
import Layout from '@/components/Layout';

import Dashboard from '@/pages/Dashboard';
import Sources from '@/pages/Sources';
import Destinations from '@/pages/Destinations';
import Syncs from '@/pages/Syncs';
import Runs from '@/pages/Runs';
import Customers from '@/pages/Customers';
import CustomerProfile from '@/pages/CustomerProfile';
import Segments from '@/pages/Segments';
import SegmentEditor from '@/pages/SegmentEditor';
import Activations from '@/pages/Activations';
import DataExplorer from '@/pages/DataExplorer';
import Reference from '@/pages/Reference';
import AskC360 from '@/pages/AskC360';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30000,
      retry: 1,
    },
  },
});

class RouteErrorBoundary extends React.Component<
  { children: ReactNode },
  { error: Error | null }
> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  override componentDidCatch(error: Error) {
    // eslint-disable-next-line no-console
    console.error('Route render failed', error);
  }

  override render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="p-6">
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <div className="font-semibold mb-1">Page failed to load</div>
          <div className="font-mono whitespace-pre-wrap">{this.state.error.message}</div>
        </div>
      </div>
    );
  }
}

function AppShell() {
  return (
    <Layout>
      <Outlet />
    </Layout>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <BrowserRouter>
          <RouteErrorBoundary>
            <Routes>
              <Route path="/" element={<AppShell />}>
                <Route index element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/customers" element={<Customers />} />
                <Route path="/customers/:id" element={<CustomerProfile />} />
                <Route path="/segments" element={<Segments />} />
                <Route path="/segments/:id" element={<SegmentEditor />} />
                <Route path="/explorer" element={<DataExplorer />} />
                <Route path="/reference" element={<Reference />} />
                <Route path="/ask" element={<AskC360 />} />
                <Route path="/activations" element={<Activations />} />
                <Route path="/sources" element={<Sources />} />
                <Route path="/destinations" element={<Destinations />} />
                <Route path="/syncs" element={<Syncs />} />
                <Route path="/syncs/:id" element={<Syncs />} />
                <Route path="/runs" element={<Runs />} />
              </Route>
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </RouteErrorBoundary>
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
