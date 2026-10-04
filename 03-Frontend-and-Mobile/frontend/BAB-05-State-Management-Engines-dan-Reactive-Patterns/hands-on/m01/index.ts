// Core Types
type Subscriber = {
  update(): void;
  flags: number;
};

const FLAG_CLEAN = 0;
const FLAG_CHECK = 1 << 0;
const FLAG_DIRTY = 1 << 1;

// Global Tracking Context
let activeSubscriber: Subscriber | null = null;
const subscriberStack: (Subscriber | null)[] = [];

let isBatching = false;
const pendingEffects: Set<Subscriber> = new Set();

export function pushContext(sub: Subscriber | null): void {
  subscriberStack.push(activeSubscriber);
  activeSubscriber = sub;
}

export function popContext(): void {
  activeSubscriber = subscriberStack.pop() ?? null;
}

export function batch(fn: () => void): void {
  const prevBatching = isBatching;
  isBatching = true;
  try {
    fn();
  } finally {
    isBatching = prevBatching;
    if (!isBatching) {
      flushEffects();
    }
  }
}

function flushEffects(): void {
  while (pendingEffects.size > 0) {
    const effectsToRun = Array.from(pendingEffects);
    pendingEffects.clear();
    for (const effect of effectsToRun) {
      effect.update();
    }
  }
}

// 1. SIGNAL INTERFACE & CLASS
export interface Signal<T> {
  get(): T;
  set(newValue: T): void;
}

export class SignalNode<T> implements Signal<T> {
  private value: T;
  private subscribers: Set<Subscriber> = new Set();

  constructor(initialValue: T) {
    this.value = initialValue;
  }

  get(): T {
    if (activeSubscriber !== null) {
      this.subscribers.add(activeSubscriber);
    }
    return this.value;
  }

  set(newValue: T): void {
    if (!Object.is(this.value, newValue)) {
      this.value = newValue;
      this.notify();
    }
  }

  private notify(): void {
    for (const sub of this.subscribers) {
      sub.flags |= FLAG_DIRTY;
      if (isBatching) {
        pendingEffects.add(sub);
      } else {
        sub.update();
      }
    }
  }

  unsubscribe(sub: Subscriber): void {
    this.subscribers.delete(sub);
  }
}

export function createSignal<T>(initialValue: T): [() => T, (val: T) => void] {
  const node = new SignalNode(initialValue);
  return [() => node.get(), (val: T) => node.set(val)];
}

// 2. COMPUTED INTERFACE & CLASS
export class ComputedNode<T> implements Subscriber {
  private fn: () => T;
  private cachedValue!: T;
  private dependencies: Set<SignalNode<any>> = new Set();
  private subscribers: Set<Subscriber> = new Set();
  public flags: number = FLAG_DIRTY;

  constructor(fn: () => T) {
    this.fn = fn;
  }

  get(): T {
    if (activeSubscriber !== null) {
      this.subscribers.add(activeSubscriber);
    }

    if (this.flags !== FLAG_CLEAN) {
      this.recompute();
    }

    return this.cachedValue;
  }

  update(): void {
    if ((this.flags & FLAG_DIRTY) === 0) {
      this.flags |= FLAG_CHECK;
      for (const sub of this.subscribers) {
        sub.update();
      }
    }
  }

  private recompute(): void {
    // Dynamic tracking cleanup
    for (const dep of this.dependencies) {
      dep.unsubscribe(this);
    }
    this.dependencies.clear();

    pushContext(this);
    try {
      const nextValue = this.fn();
      if (!Object.is(this.cachedValue, nextValue)) {
        this.cachedValue = nextValue;
      }
      this.flags = FLAG_CLEAN;
    } finally {
      popContext();
    }
  }
}

export function createComputed<T>(fn: () => T): () => T {
  const node = new ComputedNode(fn);
  return () => node.get();
}

// 3. EFFECT INTERFACE & IMPLEMENTATION
export class EffectNode implements Subscriber {
  private fn: () => void;
  public flags: number = FLAG_DIRTY;

  constructor(fn: () => void) {
    this.fn = fn;
    this.run();
  }

  run(): void {
    pushContext(this);
    try {
      this.fn();
      this.flags = FLAG_CLEAN;
    } finally {
      popContext();
    }
  }

  update(): void {
    this.flags |= FLAG_DIRTY;
    if (isBatching) {
      pendingEffects.add(this);
    } else {
      this.run();
    }
  }
}

export function createEffect(fn: () => void): void {
  new EffectNode(fn);
}
