<!-- components/TransactionDrawer.vue -->
<script setup lang="ts">
import {
  ref,
  watch,
  onMounted,
  onUnmounted,
  nextTick
} from 'vue';

interface TransactionDetail {
  id: string;
  referenceNumber: string;
  amount: number;
  currency: string;
  timestamp: number;
}

const props = defineProps<{
  isOpen: boolean;
  transaction: TransactionDetail | null;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'commit-override', id: string, note: string): void;
}>();

const drawerContainerRef = ref<HTMLElement | null>(null);
const overrideNote = ref<string>('');
const previousActiveElement = ref<HTMLElement | null>(null);

// Trap Focus Implementation untuk Kepatuhan WCAG AA Accessibility
const handleKeyDown = (event: KeyboardEvent) => {
  if (event.key === 'Escape') {
    emit('close');
    return;
  }

  if (event.key !== 'Tab' || !drawerContainerRef.value) {
    return;
  }

  const focusableElements = drawerContainerRef.value.querySelectorAll<HTMLElement>(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );

  if (focusableElements.length === 0) return;

  const firstElement = focusableElements[0];
  const lastElement = focusableElements[focusableElements.length - 1];

  if (event.shiftKey) {
    if (document.activeElement === firstElement) {
      lastElement.focus();
      event.preventDefault();
    }
  } else {
    if (document.activeElement === lastElement) {
      firstElement.focus();
      event.preventDefault();
    }
  }
};

watch(
  () => props.isOpen,
  async (newVal) => {
    if (newVal) {
      previousActiveElement.value = document.activeElement as HTMLElement;
      window.addEventListener('keydown', handleKeyDown);
      await nextTick();
      drawerContainerRef.value?.focus();
    } else {
      window.removeEventListener('keydown', handleKeyDown);
      if (previousActiveElement.value) {
        previousActiveElement.value.focus();
      }
    }
  }
);

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown);
});

const submitOverride = () => {
  if (props.transaction) {
    emit('commit-override', props.transaction.id, overrideNote.value);
    emit('close');
  }
};
</script>

<template>
  <!-- Menghindari CSS stacking context issue dengan Teleport ke body -->
  <Teleport to="body">
    <Transition name="drawer-backdrop">
      <div
        v-if="isOpen"
        class="audit-drawer-backdrop"
        @click="emit('close')"
        aria-hidden="true"
      />
    </Transition>

    <Transition name="drawer-slide">
      <aside
        v-if="isOpen"
        ref="drawerContainerRef"
        class="audit-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="drawer-title"
        tabindex="-1"
      >
        <header class="drawer-header">
          <h2 id="drawer-title">Inspection: {{ transaction?.referenceNumber }}</h2>
          <button
            class="close-btn"
            @click="emit('close')"
            aria-label="Close Inspection Drawer"
          >
            &times;
          </button>
        </header>

        <main class="drawer-body" v-if="transaction">
          <section class="metric-row">
            <span class="label">Amount:</span>
            <span class="value">{{ transaction.currency }} {{ transaction.amount.toLocaleString() }}</span>
          </section>
          <section class="metric-row">
            <span class="label">Timestamp:</span>
            <span class="value">{{ new Date(transaction.timestamp).toISOString() }}</span>
          </section>

          <div class="override-form">
            <label for="override-note">Audit Adjustment Note:</label>
            <textarea
              id="override-note"
              v-model="overrideNote"
              rows="4"
              placeholder="Provide reason for audit override..."
            ></textarea>
          </div>
        </main>

        <footer class="drawer-footer">
          <button class="btn btn-secondary" @click="emit('close')">Cancel</button>
          <button class="btn btn-primary" @click="submitOverride">Submit Override</button>
        </footer>
      </aside>
    </Transition>
  </Teleport>
</template>

<style scoped>
.audit-drawer-backdrop {
  position: fixed;
  inset: 0;
  background-color: rgba(15, 23, 42, 0.6);
  z-index: 9998;
  backdrop-filter: blur(2px);
}

.audit-drawer {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: 480px;
  background-color: #ffffff;
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.15);
  z-index: 9999;
  display: flex;
  flex-direction: column;
  outline: none;
  /* GPU Compositing Enforcer */
  will-change: transform;
}

.drawer-header {
  padding: 16px 24px;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #64748b;
}

.drawer-body {
  padding: 24px;
  flex: 1;
  overflow-y: auto;
}

.metric-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}

.override-form {
  margin-top: 24px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.override-form textarea {
  width: 100%;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  padding: 8px;
  font-family: inherit;
}

.drawer-footer {
  padding: 16px 24px;
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.btn {
  padding: 8px 16px;
  border-radius: 6px;
  font-weight: 500;
  cursor: pointer;
}

.btn-secondary {
  background: #f1f5f9;
  border: 1px solid #cbd5e1;
}

.btn-primary {
  background: #0284c7;
  color: #ffffff;
  border: none;
}

/* =========================================================================
   PERFORMANCE-ORIENTED CSS TRANSITIONS (COMPOSITOR-ONLY PROPERTIES)
   ========================================================================= */

/* Backdrop: Fade (Opacity Only) */
.drawer-backdrop-enter-active,
.drawer-backdrop-leave-active {
  transition: opacity 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.drawer-backdrop-enter-from,
.drawer-backdrop-leave-to {
  opacity: 0;
}

.drawer-backdrop-enter-to,
.drawer-backdrop-leave-from {
  opacity: 1;
}

/* Panel: Slide (Transform Only) */
.drawer-slide-enter-active {
  transition: transform 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}

.drawer-slide-leave-active {
  transition: transform 0.25s cubic-bezier(0.7, 0, 0.84, 0);
}

.drawer-slide-enter-from {
  transform: translate3d(100%, 0, 0);
}

.drawer-slide-enter-to {
  transform: translate3d(0, 0, 0);
}

.drawer-slide-leave-from {
  transform: translate3d(0, 0, 0);
}

.drawer-slide-leave-to {
  transform: translate3d(100%, 0, 0);
}
</style>
