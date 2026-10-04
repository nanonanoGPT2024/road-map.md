/**
 * @file safe_depth_traversal.c
 * @brief Traversal Pohon Data Bersarang Ekstrem: Rekursi Naif vs Explicit Heap Stack
 * Kompilasi: gcc -Wall -Wextra -O2 safe_depth_traversal.c -o safe_traversal
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>

#define MAX_SAFE_DEPTH 1000000 // 1 Juta Kedalaman
#define STACK_CAPACITY 65536

typedef struct TreeNode {
    int64_t value;
    struct TreeNode *next_child;
} TreeNode;

// -------------------------------------------------------------
// METODE 1: Rekursif Naif (Rentan Stack Overflow)
// -------------------------------------------------------------
int64_t sum_tree_recursive(const TreeNode *root, size_t *current_depth) {
    if (root == NULL) return 0;
    
    (*current_depth)++;
    // PERINGATAN: Pada sistem produksi, penumpukan frame di sini akan memicu SIGSEGV
    int64_t sub_total = sum_tree_recursive(root->next_child, current_depth);
    return root->value + sub_total;
}

// -------------------------------------------------------------
// METODE 2: Explicit Heap Stack (Aman dari Keterbatasan Ukuran Thread Stack)
// -------------------------------------------------------------
typedef struct {
    const TreeNode **nodes;
    size_t top;
    size_t capacity;
} ExplicitStack;

static ExplicitStack* create_stack(size_t capacity) {
    ExplicitStack *stack = (ExplicitStack *)malloc(sizeof(ExplicitStack));
    if (!stack) return NULL;
    
    stack->nodes = (const TreeNode **)malloc(capacity * sizeof(TreeNode *));
    if (!stack->nodes) {
        free(stack);
        return NULL;
    }
    stack->top = 0;
    stack->capacity = capacity;
    return stack;
}

static void free_stack(ExplicitStack *stack) {
    if (stack) {
        free(stack->nodes);
        free(stack);
    }
}

static bool push_stack(ExplicitStack *stack, const TreeNode *node) {
    if (stack->top >= stack->capacity) {
        // Dinamis menggandakan kapasitas jika stack manual meluap
        size_t new_cap = stack->capacity * 2;
        const TreeNode **new_nodes = (const TreeNode **)realloc(stack->nodes, new_cap * sizeof(TreeNode *));
        if (!new_nodes) return false;
        
        stack->nodes = new_nodes;
        stack->capacity = new_cap;
    }
    stack->nodes[stack->top++] = node;
    return true;
}

static const TreeNode* pop_stack(ExplicitStack *stack) {
    if (stack->top == 0) return NULL;
    return stack->nodes[--stack->top];
}

// Traversal Iteratif Bebas Risiko Stack Frame Overflow
bool sum_tree_iterative(const TreeNode *root, int64_t *out_sum) {
    if (!root || !out_sum) return false;

    ExplicitStack *stack = create_stack(1024);
    if (!stack) return false;

    int64_t total = 0;
    const TreeNode *curr = root;

    while (curr != NULL || stack->top > 0) {
        while (curr != NULL) {
            if (!push_stack(stack, curr)) {
                free_stack(stack);
                return false; // Alokasi heap gagal
            }
            curr = curr->next_child;
        }

        curr = pop_stack(stack);
        total += curr->value;
        curr = NULL; // Telusuri node berikutnya
    }

    *out_sum = total;
    free_stack(stack);
    return true;
}

// -------------------------------------------------------------
// DRIVER TEST
// -------------------------------------------------------------
int main(void) {
    // Alokasikan deep chain node secara linier di Heap
    const size_t test_depth = 50000; // Cukup untuk menguji ketahanan
    printf("[*] Membangun Linked-Chain sepanjang %zu node...\n", test_depth);
    
    TreeNode *head = (TreeNode *)malloc(sizeof(TreeNode));
    head->value = 1;
    head->next_child = NULL;

    TreeNode *curr = head;
    for (size_t i = 1; i < test_depth; ++i) {
        TreeNode *node = (TreeNode *)malloc(sizeof(TreeNode));
        node->value = 1;
        node->next_child = NULL;
        curr->next_child = node;
        curr = node;
    }

    printf("[+] Konstruksi selesai.\n");

    // Uji Pendekatan Rekursif Aman
    size_t depth_counter = 0;
    printf("[*] Menjalankan Traversal Iteratif (Explicit Heap Stack)...\n");
    int64_t sum_iter = 0;
    if (sum_tree_iterative(head, &sum_iter)) {
        printf("[SUCCESS] Total Perhitungan Iteratif: %ld\n", (long)sum_iter);
    } else {
        printf("[ERROR] Iterative Traversal Gagal.\n");
    }

    // Uji Coba Rekursif Naif (Awas Stack Overflow jika test_depth > batasan stack OS)
    printf("[*] Menjalankan Traversal Rekursif Naif (Depth Monitor)...\n");
    int64_t sum_rec = sum_tree_recursive(head, &depth_counter);
    printf("[SUCCESS] Total Perhitungan Rekursif: %ld (Mencapai Depth: %zu)\n", (long)sum_rec, depth_counter);

    // Dealokasi Memori
    curr = head;
    while (curr != NULL) {
        TreeNode *temp = curr->next_child;
        free(curr);
        curr = temp;
    }
    
    return 0;
}
