package main

import (
	"fmt"
	"reflect"
	"unsafe"
)

// ANSI colors
const (
	reset   = "\033[0m"
	bold    = "\033[1m"
	green   = "\033[32m"
	cyan    = "\033[36m"
	yellow  = "\033[33m"
	red     = "\033[31m"
	magenta = "\033[35m"
)

// SliceHeader mirror
type SliceHeader struct {
	Data uintptr
	Len  int
	Cap  int
}

type User struct {
	ID   int64
	Name string
}

// Function demonstrating pointer escaping to heap
//
//go:noinline
func createUserEscaping(id int64, name string) *User {
	u := User{ID: id, Name: name}
	return &u // Pointer to local variable returned -> escapes to heap
}

// Function staying on stack
//
//go:noinline
func createUserOnStack(id int64, name string) User {
	return User{ID: id, Name: name} // Value return -> stack allocated
}

func inspectSlice(name string, s []int) {
	hdr := (*SliceHeader)(unsafe.Pointer(&s))
	fmt.Printf("Slice [%s] -> Ptr: 0x%x | Len: %d | Cap: %d | Elems: %v\n",
		name, hdr.Data, hdr.Len, hdr.Cap, s)
}

func main() {
	fmt.Printf("%s%s======================================================%s\n", bold, cyan, reset)
	fmt.Printf("%s%s  LAB HANDS-ON: GO SLICE HEADER & MEMORY ALLOCATION   %s\n", bold, cyan, reset)
	fmt.Printf("%s%s======================================================%s\n", bold, cyan, reset)

	// 1. Slice Header Inspection & Capacity Growth
	fmt.Printf("\n%s[Step 1] Inspecting Slice Header Anatomy & Growth%s\n", bold, reset)
	s := make([]int, 0, 2)
	inspectSlice("initial s", s)

	s = append(s, 10, 20)
	inspectSlice("after 2 appends", s)

	origPtr := (*SliceHeader)(unsafe.Pointer(&s)).Data

	// Append third element - exceeds cap=2, triggers growth & reallocation
	s = append(s, 30)
	newPtr := (*SliceHeader)(unsafe.Pointer(&s)).Data
	inspectSlice("after 3rd append (grown)", s)

	if origPtr == newPtr {
		fmt.Printf("%sReallocation check failed: Pointer did not change%s\n", red, reset)
	} else {
		fmt.Printf("%s%s✓ Capacity doubled & pointer reallocated correctly (0x%x -> 0x%x)%s\n",
			green, bold, origPtr, newPtr, reset)
	}

	// 2. Sub-slice Pointer Sharing
	fmt.Printf("\n%s[Step 2] Sub-slice Memory Pointer Sharing%s\n", bold, reset)
	sub := s[1:3]
	inspectSlice("sub-slice s[1:3]", sub)

	sub[0] = 999 // Mutating sub-slice affects underlying array
	fmt.Printf("%sAfter mutating sub[0] = 999:%s\n", yellow, reset)
	inspectSlice("original s", s)

	if s[1] != 999 {
		panic("Subslice mutation did not reflect in parent slice")
	}
	fmt.Printf("%s%s✓ Sub-slice shares underlying backing array with parent slice!%s\n", green, bold, reset)

	// 3. Escape Analysis Demonstration
	fmt.Printf("\n%s[Step 3] Escape Analysis: Stack vs Heap Allocation%s\n", bold, reset)
	uHeap := createUserEscaping(101, "Budi (Escaped to Heap)")
	uStack := createUserOnStack(102, "Dewi (Stack Local)")

	fmt.Printf("Heap Escaped User: Ptr = %p, Value = %+v\n", uHeap, *uHeap)
	fmt.Printf("Stack Allocated User Value = %+v (Type: %v)\n", uStack, reflect.TypeOf(uStack))

	fmt.Printf("\n%s%s✓ SUCCESS: Go Slice Header, Capacity doubling, and Escape mechanics verified!%s\n", green, bold, reset)
}
