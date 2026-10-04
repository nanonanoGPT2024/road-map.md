// app/features/tenant/tenant-scope.component.ts
import { 
  Component, 
  Input, 
  inject, 
  Host, 
  ChangeDetectionStrategy 
} from '@angular/core';
import { 
  TENANT_CONFIG, 
  TENANT_SESSION_CONTEXT 
} from '../../core/tenant/tenant.tokens';
import { TenantCryptoService } from '../../core/tenant/tenant-crypto.service';
import { IsolatedTenantSessionService } from '../../core/tenant/isolated-tenant-session.service';
import { TenantConfig } from '../../core/tenant/tenant.types';

@Component({
  selector: 'app-tenant-scope-wrapper',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [
    // Sub-pohon injector terisolasi per batas DOM komponen wrapper
    TenantCryptoService,
    {
      provide: TENANT_SESSION_CONTEXT,
      useClass: IsolatedTenantSessionService
    },
    {
      provide: TENANT_CONFIG,
      useFactory: (comp: TenantScopeWrapperComponent): TenantConfig => {
        return {
          tenantId: comp.tenantId,
          currency: comp.currency,
          cryptoSignatureAlgorithm: comp.algo
        };
      },
      deps: [TenantScopeWrapperComponent]
    }
  ],
  template: `
    <div class="tenant-boundary p-6 border-2 border-indigo-700 rounded-lg">
      <h3 class="text-xl font-bold">Scope Aktif: {{ session.getSessionData().tenantId }}</h3>
      <ng-content></ng-content>
    </div>
  `
})
export class TenantScopeWrapperComponent {
  @Input({ required: true }) tenantId!: string;
  @Input({ required: true }) currency!: string;
  @Input({ required: true }) algo: 'SHA-256' | 'RSA-PSS' = 'SHA-256';

  protected readonly session = inject(TENANT_SESSION_CONTEXT, { self: true });
}
