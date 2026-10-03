package main

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"time"
)

// ANSI colors
const (
	reset  = "\033[0m"
	bold   = "\033[1m"
	green  = "\033[32m"
	cyan   = "\033[36m"
	yellow = "\033[33m"
	red    = "\033[31m"
)

// Sentinel domain errors
var (
	ErrDatabaseTimeout = errors.New("database query timed out")
	ErrUserNotFound    = errors.New("user entity not found")
)

// 1. Panic Recovery Middleware
func RecoveryMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if rec := recover(); rec != nil {
				fmt.Printf("  %s[PANIC RECOVERED]%s Caught unexpected panic: %v\n", red, reset, rec)
				http.Error(w, "500 Internal Server Error (Panic Shield)", http.StatusInternalServerError)
			}
		}()
		next.ServeHTTP(w, r)
	})
}

// 2. Simulated Repository with Error Wrapping
func fetchUserData(ctx context.Context, id int) (string, error) {
	select {
	case <-time.After(20 * time.Millisecond):
		if id == 404 {
			return "", fmt.Errorf("repository layer: %w (id=%d)", ErrUserNotFound, id)
		}
		if id == 999 {
			panic("nil pointer dereference inside database driver!")
		}
		return fmt.Sprintf("User#%d", id), nil
	case <-ctx.Done():
		return "", fmt.Errorf("service layer context aborted: %w", ErrDatabaseTimeout)
	}
}

// 3. User HTTP Handler
func userHandler(w http.ResponseWriter, r *http.Request) {
	idStr := r.URL.Query().Get("id")
	var id int
	fmt.Sscanf(idStr, "%d", &id)

	data, err := fetchUserData(r.Context(), id)
	if err != nil {
		if errors.Is(err, ErrUserNotFound) {
			fmt.Printf("  %s[DOMAIN ERROR]%s Handled gracefully: %v\n", yellow, reset, err)
			http.Error(w, "User Not Found", http.StatusNotFound)
			return
		}
		if errors.Is(err, ErrDatabaseTimeout) {
			fmt.Printf("  %s[TIMEOUT ERROR]%s Handled gracefully: %v\n", red, reset, err)
			http.Error(w, "Gateway Timeout", http.StatusGatewayTimeout)
			return
		}
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	fmt.Fprintf(w, "OK: %s", data)
}

func main() {
	fmt.Printf("%s%s======================================================%s\n", bold, cyan, reset)
	fmt.Printf("%s%s  LAB HANDS-ON: GO ERROR WRAPPING & PANIC RECOVERY    %s\n", bold, cyan, reset)
	fmt.Printf("%s%s======================================================%s\n", bold, cyan, reset)

	// Build middleware chain
	handler := RecoveryMiddleware(http.HandlerFunc(userHandler))

	// Test 1: Successful Request
	fmt.Printf("\n%s[Test 1] Successful Request (id=1)%s\n", bold, reset)
	req1 := httptest.NewRequest(http.MethodGet, "/user?id=1", nil)
	rec1 := httptest.NewRecorder()
	handler.ServeHTTP(rec1, req1)
	fmt.Printf("Status: %d | Body: %s\n", rec1.Code, rec1.Body.String())
	if rec1.Code != http.StatusOK {
		panic("Expected 200 OK")
	}

	// Test 2: Domain Error with errors.Is wrapping check
	fmt.Printf("\n%s[Test 2] Domain Error (id=404 -> ErrUserNotFound)%s\n", bold, reset)
	req2 := httptest.NewRequest(http.MethodGet, "/user?id=404", nil)
	rec2 := httptest.NewRecorder()
	handler.ServeHTTP(rec2, req2)
	fmt.Printf("Status: %d | Body: %s\n", rec2.Code, rec2.Body.String())
	if rec2.Code != http.StatusNotFound {
		panic("Expected 404 Not Found")
	}

	// Test 3: Panic Recovery Protection
	fmt.Printf("\n%s[Test 3] Panic Recovery Protection (id=999 -> Triggers Panic)%s\n", bold, reset)
	req3 := httptest.NewRequest(http.MethodGet, "/user?id=999", nil)
	rec3 := httptest.NewRecorder()
	handler.ServeHTTP(rec3, req3)
	fmt.Printf("Status: %d | Body: %s\n", rec3.Code, rec3.Body.String())
	if rec3.Code != http.StatusInternalServerError {
		panic("Expected 500 Internal Server Error from recovery middleware")
	}

	fmt.Printf("\n%s%s✓ SUCCESS: Go Error Handling, Wrapping, and Panic Recovery verified!%s\n", green, bold, reset)
}
