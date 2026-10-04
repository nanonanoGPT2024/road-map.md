// src/app/router/AppRouter.tsx
import React, { Suspense } from 'react';
import { 
  createBrowserRouter, 
  RouterProvider, 
  RouteObject, 
  Link, 
  Outlet 
} from 'react-router-dom';
import { lazyWithPreload } from '../../lib/lazy-with-preload';

// 1. Lazy loaded components with preload capability
const AnalyticsDashboard = lazyWithPreload(
  () => import('../../features/analytics/routes/AnalyticsPage')
);
const SettingsPage = lazyWithPreload(
  () => import('../../features/settings/routes/SettingsPage')
);

// Fallback skeleton
const PageLoadingFallback = () => (
  <div style={{ padding: '2rem', display: 'flex', gap: '1rem', flexDirection: 'column' }}>
    <div style={{ width: '40%', height: '24px', background: '#e2e8f0', borderRadius: '4px' }} />
    <div style={{ width: '100%', height: '200px', background: '#f1f5f9', borderRadius: '8px' }} />
  </div>
);

// Layout Shell
const RootLayout = () => {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '240px 1fr', minHeight: '100vh' }}>
      <aside style={{ borderRight: '1px solid #e2e8f0', padding: '1rem' }}>
        <nav style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {/* Intent-based Prefetch: memicu chunk download saat cursor berada di atas link */}
          <Link 
            to="/analytics" 
            onPointerEnter={() => AnalyticsDashboard.preload()}
            style={{ textDecoration: 'none', color: '#0f172a', fontWeight: 500 }}
          >
            Analytics
          </Link>
          <Link 
            to="/settings" 
            onPointerEnter={() => SettingsPage.preload()}
            style={{ textDecoration: 'none', color: '#0f172a', fontWeight: 500 }}
          >
            Settings
          </Link>
        </nav>
      </aside>
      <main>
        <Suspense fallback={<PageLoadingFallback />}>
          <Outlet />
        </Suspense>
      </main>
    </div>
  );
};

const routes: RouteObject[] = [
  {
    path: '/',
    element: <RootLayout />,
    children: [
      {
        path: 'analytics',
        element: <AnalyticsDashboard />,
      },
      {
        path: 'settings',
        element: <SettingsPage />,
      },
    ],
  },
];

const router = createBrowserRouter(routes);

export const AppRouter: React.FC = () => {
  return <RouterProvider router={router} />;
};
