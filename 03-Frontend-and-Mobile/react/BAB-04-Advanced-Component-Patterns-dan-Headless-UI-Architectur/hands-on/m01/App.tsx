import * as React from 'react';

// ==========================================
// 1. DOM UTILITIES & TYPES
// ==========================================

export interface ComboboxOptionItem {
  id: string;
  value: string;
  label: string;
  disabled?: boolean;
}

export interface ComboboxState<T extends ComboboxOptionItem> {
  isOpen: boolean;
  highlightedIndex: number;
  selectedItem: T | null;
  inputValue: string;
}

export type ComboboxAction<T extends ComboboxOptionItem> =
  | { type: 'INPUT_CHANGE'; payload: string }
  | { type: 'ITEM_CLICK'; payload: T }
  | { type: 'NAVIGATE'; payload: number }
  | { type: 'OPEN' }
  | { type: 'CLOSE' }
  | { type: 'RESET' };

export type ComboboxStateReducer<T extends ComboboxOptionItem> = (
  state: ComboboxState<T>,
  action: ComboboxAction<T>
) => ComboboxState<T>;

function composeEvents<E extends React.SyntheticEvent | Event>(
  userHandler?: (e: E) => void,
  internalHandler?: (e: E) => void
) {
  return (e: E) => {
    userHandler?.(e);
    if (!e.defaultPrevented) {
      internalHandler?.(e);
    }
  };
}

// ==========================================
// 2. CORE HEADLESS ENGINE (HOOK)
// ==========================================

export interface UseComboboxProps<T extends ComboboxOptionItem> {
  items: T[];
  itemToString?: (item: T | null) => string;
  onSelectedItemChange?: (item: T | null) => void;
  stateReducer?: ComboboxStateReducer<T>;
  initialSelectedItem?: T | null;
}

export function useComboboxCore<T extends ComboboxOptionItem>({
  items,
  itemToString = (item) => (item ? item.label : ''),
  onSelectedItemChange,
  stateReducer,
  initialSelectedItem = null,
}: UseComboboxProps<T>) {
  const defaultReducer: ComboboxStateReducer<T> = (state, action) => {
    switch (action.type) {
      case 'INPUT_CHANGE':
        return {
          ...state,
          isOpen: true,
          inputValue: action.payload,
          highlightedIndex: items.findIndex((i) => !i.disabled),
        };
      case 'ITEM_CLICK':
        return {
          ...state,
          isOpen: false,
          selectedItem: action.payload,
          inputValue: itemToString(action.payload),
          highlightedIndex: -1,
        };
      case 'NAVIGATE':
        return {
          ...state,
          highlightedIndex: action.payload,
        };
      case 'OPEN':
        return {
          ...state,
          isOpen: true,
          highlightedIndex: state.selectedItem
            ? items.findIndex((i) => i.id === state.selectedItem?.id)
            : items.findIndex((i) => !i.disabled),
        };
      case 'CLOSE':
        return {
          ...state,
          isOpen: false,
          highlightedIndex: -1,
          inputValue: state.selectedItem ? itemToString(state.selectedItem) : '',
        };
      case 'RESET':
        return {
          isOpen: false,
          highlightedIndex: -1,
          selectedItem: null,
          inputValue: '',
        };
      default:
        return state;
    }
  };

  const combinedReducer = React.useCallback(
    (s: ComboboxState<T>, a: ComboboxAction<T>) => {
      const nextState = defaultReducer(s, a);
      return stateReducer ? stateReducer(nextState, a) : nextState;
    },
    [stateReducer, items, itemToString]
  );

  const [state, dispatch] = React.useReducer(combinedReducer, {
    isOpen: false,
    highlightedIndex: -1,
    selectedItem: initialSelectedItem,
    inputValue: itemToString(initialSelectedItem),
  });

  const generatedId = React.useId();
  const listboxId = `combobox-listbox-${generatedId}`;
  const inputId = `combobox-input-${generatedId}`;

  // Notify parent upon item selection
  const previousSelected = React.useRef(state.selectedItem);
  React.useEffect(() => {
    if (previousSelected.current !== state.selectedItem) {
      previousSelected.current = state.selectedItem;
      onSelectedItemChange?.(state.selectedItem);
    }
  }, [state.selectedItem, onSelectedItemChange]);

  // Prop Getters
  const getInputProps = React.useCallback(
    (props: React.InputHTMLAttributes<HTMLInputElement> = {}) => {
      const activeOption = items[state.highlightedIndex];
      const activeDescendantId =
        state.isOpen && activeOption ? `${listboxId}-option-${activeOption.id}` : undefined;

      return {
        ...props,
        'id': inputId,
        'role': 'combobox',
        'aria-autocomplete': 'list' as const,
        'aria-expanded': state.isOpen,
        'aria-haspopup': 'listbox' as const,
        'aria-controls': listboxId,
        'aria-activedescendant': activeDescendantId,
        'value': state.inputValue,
        onChange: composeEvents(props.onChange, (e: React.ChangeEvent<HTMLInputElement>) => {
          dispatch({ type: 'INPUT_CHANGE', payload: e.target.value });
        }),
        onKeyDown: composeEvents(props.onKeyDown, (e: React.KeyboardEvent<HTMLInputElement>) => {
          if (!state.isOpen && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
            e.preventDefault();
            dispatch({ type: 'OPEN' });
            return;
          }

          if (state.isOpen) {
            if (e.key === 'ArrowDown') {
              e.preventDefault();
              let nextIdx = state.highlightedIndex + 1;
              while (nextIdx < items.length && items[nextIdx].disabled) {
                nextIdx++;
              }
              if (nextIdx < items.length) {
                dispatch({ type: 'NAVIGATE', payload: nextIdx });
              }
            } else if (e.key === 'ArrowUp') {
              e.preventDefault();
              let prevIdx = state.highlightedIndex - 1;
              while (prevIdx >= 0 && items[prevIdx].disabled) {
                prevIdx--;
              }
              if (prevIdx >= 0) {
                dispatch({ type: 'NAVIGATE', payload: prevIdx });
              }
            } else if (e.key === 'Enter') {
              e.preventDefault();
              if (state.highlightedIndex >= 0 && items[state.highlightedIndex]) {
                const item = items[state.highlightedIndex];
                if (!item.disabled) {
                  dispatch({ type: 'ITEM_CLICK', payload: item });
                }
              }
            } else if (e.key === 'Escape') {
              e.preventDefault();
              dispatch({ type: 'CLOSE' });
            }
          }
        }),
        onFocus: composeEvents(props.onFocus, () => {
          if (!state.isOpen) dispatch({ type: 'OPEN' });
        }),
      };
    },
    [state, items, listboxId, inputId]
  );

  const getListboxProps = React.useCallback(
    (props: React.HTMLAttributes<HTMLUListElement> = {}) => ({
      ...props,
      id: listboxId,
      role: 'listbox',
      'aria-labelledby': inputId,
      tabIndex: -1,
    }),
    [listboxId, inputId]
  );

  const getOptionProps = React.useCallback(
    (item: T, index: number, props: React.LiHTMLAttributes<HTMLLIElement> = {}) => {
      const isHighlighted = state.highlightedIndex === index;
      const isSelected = state.selectedItem?.id === item.id;

      return {
        ...props,
        'id': `${listboxId}-option-${item.id}`,
        'role': 'option',
        'aria-selected': isSelected,
        'aria-disabled': item.disabled,
        'data-highlighted': isHighlighted ? 'true' : undefined,
        onClick: composeEvents(props.onClick, () => {
          if (!item.disabled) {
            dispatch({ type: 'ITEM_CLICK', payload: item });
          }
        }),
      };
    },
    [state.highlightedIndex, state.selectedItem, listboxId]
  );

  return {
    state,
    dispatch,
    getInputProps,
    getListboxProps,
    getOptionProps,
  };
}

// ==========================================
// 3. COMPOUND COMPONENTS CONTEXT WRAPPER
// ==========================================

interface ComboboxContextValue<T extends ComboboxOptionItem> {
  state: ComboboxState<T>;
  getInputProps: ReturnType<typeof useComboboxCore<T>>['getInputProps'];
  getListboxProps: ReturnType<typeof useComboboxCore<T>>['getListboxProps'];
  getOptionProps: ReturnType<typeof useComboboxCore<T>>['getOptionProps'];
}

const ComboboxContext = React.createContext<ComboboxContextValue<any> | null>(null);

function useComboboxContext<T extends ComboboxOptionItem>() {
  const context = React.useContext(ComboboxContext);
  if (!context) {
    throw new Error('Combobox Compound Components must be used within <Combobox.Root>');
  }
  return context as ComboboxContextValue<T>;
}

export function ComboboxRoot<T extends ComboboxOptionItem>({
  children,
  items,
  onSelectedItemChange,
  stateReducer,
  initialSelectedItem,
}: UseComboboxProps<T> & { children: React.ReactNode }) {
  const combobox = useComboboxCore({
    items,
    onSelectedItemChange,
    stateReducer,
    initialSelectedItem,
  });

  const memoizedContext = React.useMemo<ComboboxContextValue<T>>(
    () => ({
      state: combobox.state,
      getInputProps: combobox.getInputProps,
      getListboxProps: combobox.getListboxProps,
      getOptionProps: combobox.getOptionProps,
    }),
    [
      combobox.state,
      combobox.getInputProps,
      combobox.getListboxProps,
      combobox.getOptionProps,
    ]
  );

  return (
    <ComboboxContext.Provider value={memoizedContext}>
      <div style={{ position: 'relative', display: 'inline-block', width: '100%' }}>
        {children}
      </div>
    </ComboboxContext.Provider>
  );
}

export const ComboboxInput = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>((props, ref) => {
  const { getInputProps } = useComboboxContext();
  const inputProps = getInputProps(props);
  return <input ref={ref} {...inputProps} />;
});
ComboboxInput.displayName = 'ComboboxInput';

export const ComboboxList = React.forwardRef<
  HTMLUListElement,
  React.HTMLAttributes<HTMLUListElement>
>((props, ref) => {
  const { state, getListboxProps } = useComboboxContext();
  if (!state.isOpen) return null;
  return <ul ref={ref} {...getListboxProps(props)} />;
});
ComboboxList.displayName = 'ComboboxList';

export interface ComboboxOptionComponentProps extends React.LiHTMLAttributes<HTMLLIElement> {
  item: ComboboxOptionItem;
  index: number;
}

export const ComboboxOption = React.forwardRef<HTMLLIElement, ComboboxOptionComponentProps>(
  ({ item, index, children, ...rest }, ref) => {
    const { getOptionProps } = useComboboxContext();
    return (
      <li ref={ref} {...getOptionProps(item, index, rest)}>
        {children || item.label}
      </li>
    );
  }
);
ComboboxOption.displayName = 'ComboboxOption';

// Export Compound Namespace
export const Combobox = {
  Root: ComboboxRoot,
  Input: ComboboxInput,
  List: ComboboxList,
  Option: ComboboxOption,
};
