// trading-terminal.component.ts
import { Component, ChangeDetectionStrategy, inject } from '@angular/core';
import { CommonModule, DecimalPipe } from '@angular/common';
import { TradingEngineStore } from './trading-engine.store';

@Component({
  selector: 'app-trading-terminal',
  standalone: true,
  imports: [CommonModule, DecimalPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="terminal-container" [class.risk-alert]="store.isMarginCallRisk()">
      <header class="header">
        <h1>Institutional Trading Desk</h1>
        <div class="balance-bar">
          <div>Balance: <strong>\${{ store.accountBalance() | number:'1.2-2' }}</strong></div>
          <div>Equity: <strong>\${{ (store.accountBalance() + store.unrealizedPnL()) | number:'1.2-2' }}</strong></div>
          <div>Used Margin: <strong>\${{ store.usedMargin() | number:'1.2-2' }}</strong></div>
          <div>Free Margin: <strong>\${{ store.freeMargin() | number:'1.2-2' }}</strong></div>
          <div>PnL: <strong [style.color]="store.unrealizedPnL() >= 0 ? 'green' : 'red'">
            \${{ store.unrealizedPnL() | number:'1.2-2' }}
          </strong></div>
        </div>
      </header>

      <div class="symbol-selector">
        @for (sym of availableSymbols; track sym) {
          <button 
            [class.active]="store.activeSymbol() === sym" 
            (click)="store.setActiveSymbol(sym)">
            {{ sym }}
          </button>
        }
      </div>

      <section class="ticker-box">
        <h2>Symbol: {{ store.activeSymbol() }}</h2>
        @if (store.currentActiveTick(); as tick) {
          <div class="tick-display">
            <span>BID: <b class="bid">{{ tick.bid | number:'1.4-4' }}</b></span>
            <span>ASK: <b class="ask">{{ tick.ask | number:'1.4-4' }}</b></span>
          </div>
        } @else {
          <p>Connecting to price feed...</p>
        }
      </section>

      <section class="positions-table">
        <h3>Open Positions</h3>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Symbol</th>
              <th>Units</th>
              <th>Entry Price</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            @for (pos of store.openPositions(); track pos.id) {
              <tr>
                <td>{{ pos.id }}</td>
                <td>{{ pos.symbol }}</td>
                <td>{{ pos.units | number }}</td>
                <td>{{ pos.entryPrice | number:'1.4-4' }}</td>
                <td>
                  <button (click)="store.closePosition(pos.id)">Liquidate</button>
                </td>
              </tr>
            }
          </tbody>
        </table>
      </section>
    </div>
  `,
  styles: [`
    .terminal-container { padding: 1.5rem; font-family: monospace; background: #0f172a; color: #f8fafc; }
    .risk-alert { border: 2px solid #ef4444; }
    .balance-bar { display: flex; gap: 1.5rem; padding: 0.5rem 0; border-bottom: 1px solid #334155; }
    .symbol-selector button { margin-right: 0.5rem; margin-top: 1rem; padding: 0.5rem 1rem; }
    .symbol-selector button.active { background: #3b82f6; color: white; font-weight: bold; }
    .ticker-box { margin: 1rem 0; padding: 1rem; background: #1e293b; border-radius: 4px; }
    .tick-display { font-size: 1.5rem; display: flex; gap: 2rem; }
    .bid { color: #22c55e; }
    .ask { color: #f43f5e; }
    table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
    th, td { text-align: left; padding: 0.5rem; border-bottom: 1px solid #334155; }
  `]
})
export class TradingTerminalComponent {
  readonly store = inject(TradingEngineStore);
  readonly availableSymbols = ['EUR/USD', 'GBP/USD', 'USD/JPY'];
}
