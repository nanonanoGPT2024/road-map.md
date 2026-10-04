// core/guards/security.guards.ts
import { inject } from '@angular/core';
import { CanMatchFn, CanActivateFn, CanDeactivateFn, Router, Route, UrlSegment } from '@angular/router';
import { AuthSessionService } from '../services/auth-session.service';
import { ComponentCanDeactivate } from '../models/auth.models';

/**
 * Mencegah chunk downloading jika user tidak memiliki role valid.
 * Mengembalikan false menyebabkan Angular melanjutkan pencarian ke rute lain (fallback).
 */
export const featureAccessCanMatchGuard = (requiredRoles: string[]): CanMatchFn => {
  return (route: Route, segments: UrlSegment[]) => {
    const authService = inject(AuthSessionService);
    
    if (!authService.isAuthenticated()) {
      return false;
    }

    return authService.hasRole(requiredRoles as any);
  };
};

/**
 * Memastikan proteksi rute detail dan validasi redirection.
 */
export const strictRoleCanActivateGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthSessionService);
  const router = inject(Router);
  const expectedRoles = route.data['roles'] as string[] | undefined;

  if (!authService.isAuthenticated()) {
    return router.createUrlTree(['/auth/login'], { queryParams: { returnUrl: state.url } });
  }

  if (expectedRoles && !authService.hasRole(expectedRoles as any)) {
    return router.createUrlTree(['/forbidden']);
  }

  return true;
};

/**
 * Menahan navigasi jika ada uncommitted memory state.
 */
export const pendingChangesCanDeactivateGuard: CanDeactivateFn<ComponentCanDeactivate> = (
  component
) => {
  if (component && typeof component.canDeactivate === 'function') {
    return component.canDeactivate() || confirm('Perubahan Anda belum tersimpan. Tinggalkan halaman?');
  }
  return true;
};
